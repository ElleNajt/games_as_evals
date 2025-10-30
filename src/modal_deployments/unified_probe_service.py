"""
Unified Modal backend for serving LLM probes with vLLM.

Single service that handles all probe types (deception, hallucination, etc.)
by loading from volume paths and returning per-token activations.
"""

import modal
import torch
import torch.nn as nn
from typing import List, Dict, Any, Optional, Tuple
import json
from transformers import AutoTokenizer
import pickle
from pathlib import Path
import os

# Configuration
DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"
N_GPU = 1  # Default to 1 GPU (A10G for 8B models)
GPU_CONFIG = "A10G"
SCALEDOWN_WINDOW = 2 * 60  # 2 minutes
TIMEOUT = 20 * 60  # 20 minutes

# Volume for storing models and probes
VOLUME = modal.Volume.from_name("unified-probe-models", create_if_missing=True)
VOLUME_PATH = "/models"
PROBES_DIR = Path(VOLUME_PATH) / "probes"

# Load HF token for accessing Llama models
if modal.is_local():
    from dotenv import load_dotenv
    load_dotenv()
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        raise ValueError("HF_TOKEN must be set in environment or .env file")
    LOCAL_HF_TOKEN_SECRET = modal.Secret.from_dict({"HF_TOKEN": hf_token})
else:
    LOCAL_HF_TOKEN_SECRET = modal.Secret.from_dict({})

# Modal image
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch>=2.0.0",
        "transformers>=4.40.0",
        "accelerate>=0.20.0",
        "numpy>=1.24.0",
        "vllm==0.6.3",  # Pin to 0.6.3 for stability
        "huggingface_hub>=0.20.0",
        "scikit-learn>=1.3.0",  # For probe loaders
        "jaxtyping>=0.2.0",
    )
)

app = modal.App("unified-probe-service", image=image)


def load_probe_from_volume(probe_path: Path) -> Tuple[nn.Module, int]:
    """
    Load a probe from the volume.
    
    Supports two formats:
    1. Apollo format: probe_head.pt with metadata (pickle)
    2. Hallucination format: probe_head.bin + probe_config.json
    
    Args:
        probe_path: Path to probe directory on volume
        
    Returns:
        (probe_head, layer_idx)
    """
    # Check for Apollo format first (.pt file)
    apollo_file = probe_path / "probe_detector.pt"
    if apollo_file.exists():
        print(f"Loading Apollo format probe from {probe_path}")
        with open(apollo_file, 'rb') as f:
            data = pickle.load(f)
        
        # Convert numpy arrays to tensors if needed
        import numpy as np
        def ensure_tensor(obj):
            if isinstance(obj, np.ndarray):
                return torch.from_numpy(obj)
            elif isinstance(obj, dict):
                return {k: ensure_tensor(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [ensure_tensor(item) for item in obj]
            return obj
        
        data = ensure_tensor(data)
        
        # Extract probe info
        layers = data["layers"]
        layer_idx = layers[0] if isinstance(layers, list) else layers
        directions = data["directions"]
        direction = directions[layer_idx] if isinstance(directions, dict) else directions
        
        # Create linear probe head
        hidden_dim = direction.shape[-1]
        probe_head = nn.Linear(hidden_dim, 1, bias=False)
        
        # Load weights (direction is the weight)
        with torch.no_grad():
            probe_head.weight.copy_(direction.view(1, -1))
        
        return probe_head, layer_idx
    
    # Check for hallucination format
    config_file = probe_path / "probe_config.json"
    weights_file = probe_path / "probe_head.bin"
    
    if config_file.exists() and weights_file.exists():
        print(f"Loading hallucination format probe from {probe_path}")
        
        # Load config
        with open(config_file) as f:
            config = json.load(f)
        
        hidden_size = config['hidden_size']
        layer_idx = config['layer_idx']
        
        # Create probe head
        probe_head = nn.Linear(hidden_size, 1, device='cpu', dtype=torch.float32)
        
        # Load weights
        state_dict = torch.load(weights_file, map_location="cpu", weights_only=True)
        probe_head.load_state_dict(state_dict)
        probe_head.eval()
        
        return probe_head, layer_idx
    
    raise ValueError(f"No valid probe found at {probe_path}. Expected probe_detector.pt or probe_head.bin+probe_config.json")


@app.cls(
    image=image,
    gpu=GPU_CONFIG,
    scaledown_window=SCALEDOWN_WINDOW,
    volumes={VOLUME_PATH: VOLUME},
    timeout=TIMEOUT,
    secrets=[LOCAL_HF_TOKEN_SECRET],
)
class UnifiedProbeService:
    """
    Unified Modal service for probe inference.
    
    Handles all probe types via volume paths and returns per-token activations.
    """
    
    model_name: str = modal.parameter(default=DEFAULT_MODEL)
    
    def __init__(self):
        self.llm = None
        self.tokenizer = None
        self.loaded_probes = {}  # Cache: {probe_path: (probe_head, layer_idx)}
    
    @modal.enter()
    def load_model(self):
        """Load vLLM model on container startup."""
        from vllm import LLM
        
        print(f"Loading vLLM model: {self.model_name}")
        
        # Initialize vLLM
        self.llm = LLM(
            model=self.model_name,
            gpu_memory_utilization=0.90,
            max_model_len=8192,
            trust_remote_code=True,
            enforce_eager=True,  # Required for hooks
            download_dir=VOLUME_PATH,
            tensor_parallel_size=N_GPU,
        )
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            token=os.environ.get("HF_TOKEN")
        )
        
        print("Model loaded successfully!")
    
    def _load_probe_if_needed(self, probe_path: str) -> Tuple[nn.Module, int]:
        """Load probe from volume if not already cached."""
        if probe_path not in self.loaded_probes:
            path = Path(probe_path)
            if not path.is_absolute():
                # Make relative paths relative to PROBES_DIR
                path = PROBES_DIR / path
            
            probe_head, layer_idx = load_probe_from_volume(path)
            
            # Move to GPU
            probe_head = probe_head.to('cuda')
            probe_head.eval()
            
            self.loaded_probes[probe_path] = (probe_head, layer_idx)
            print(f"Loaded probe from {path} (layer {layer_idx})")
        
        return self.loaded_probes[probe_path]
    
    @modal.method()
    def generate_with_probe(
        self,
        messages: List[Dict[str, str]],
        probe_path: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Generate text with per-token probe activations.
        
        Args:
            messages: Chat messages
            probe_path: Path to probe on volume (relative to /models/probes/ or absolute)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            {
                "generated_text": str,              # Full generated text
                "generated_tokens": List[str],      # List of token strings
                "token_scores": List[float],        # Raw probe score per token (pre-sigmoid)
                "prompt_num_tokens": int,           # Number of prompt tokens
                "generated_num_tokens": int,        # Number of generated tokens
            }
        """
        from vllm import SamplingParams, TokensPrompt
        
        try:
            # Load probe
            probe_head, probe_layer = self._load_probe_if_needed(probe_path)
            
            # Format conversation
            prompt_token_ids = self.tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True
            )
            prompt_num_tokens = len(prompt_token_ids)
            
            # Sampling parameters
            sampling_params = SamplingParams(
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9 if temperature > 0 else 1.0,
            )
            
            # Get model and target layer
            model = self.llm.llm_engine.model_executor.driver_worker.model_runner.model
            target_layer = model.model.layers[probe_layer]
            
            # Storage for probe scores
            token_scores = []
            first_forward = True
            
            def activation_hook(module, input, output):
                """Capture activations and score them."""
                nonlocal first_forward, token_scores
                
                # Skip first forward pass (prompt processing)
                if first_forward:
                    first_forward = False
                    return
                
                # Extract hidden states
                assert len(output) == 2
                hidden_states, residual = output
                resid_post = hidden_states + residual
                
                # Score with probe (keep on GPU)
                with torch.no_grad():
                    scores = probe_head(resid_post).squeeze(-1)
                    
                    # Handle batched generation
                    if scores.numel() == 1:
                        token_scores.append(scores.item())
                    else:
                        # Take last token
                        token_scores.append(scores[-1].item())
            
            # Register hook
            hook_handle = target_layer.register_forward_hook(activation_hook)
            
            try:
                # Generate
                outputs = self.llm.generate(
                    prompts=[TokensPrompt(prompt_token_ids=prompt_token_ids)],
                    sampling_params=sampling_params,
                    use_tqdm=False
                )
                
                # Extract tokens
                generated_ids = list(outputs[0].outputs[0].token_ids)
                
            finally:
                hook_handle.remove()
            
            # Fix alignment if needed (EOS token)
            if len(token_scores) != len(generated_ids):
                if len(token_scores) + 1 == len(generated_ids):
                    token_scores.append(0.0)  # EOS gets neutral score
            
            # Decode tokens
            generated_tokens = self.tokenizer.convert_ids_to_tokens(generated_ids)
            generated_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
            
            return {
                "generated_text": generated_text,
                "generated_tokens": generated_tokens,
                "token_scores": token_scores,
                "prompt_num_tokens": prompt_num_tokens,
                "generated_num_tokens": len(generated_ids),
            }
            
        except Exception as e:
            import traceback
            return {
                "error": f"Generation failed: {str(e)}",
                "traceback": traceback.format_exc()
            }
    
    @modal.method()
    def generate_without_probe(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Generate without probe scoring (faster)."""
        from vllm import SamplingParams
        
        try:
            # Sampling parameters
            sampling_params = SamplingParams(
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9 if temperature > 0 else 1.0,
            )
            
            # Format prompt
            prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            # Generate
            outputs = self.llm.generate(
                prompts=[prompt],
                sampling_params=sampling_params,
                use_tqdm=False
            )
            
            generated_text = outputs[0].outputs[0].text
            
            return {
                "generated_text": generated_text,
            }
            
        except Exception as e:
            return {"error": f"Generation failed: {str(e)}"}


@app.function(image=image)
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "unified-probe-service"}


if __name__ == "__main__":
    # Test locally
    with app.run():
        service = UnifiedProbeService()
        
        result = service.generate_with_probe.remote(
            messages=[{"role": "user", "content": "What is 2+2?"}],
            probe_path="deception_8b_layer12",  # Example path
            max_tokens=50
        )
        
        print(result)
