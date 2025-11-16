"""
Unified Modal backend for serving 70B LLM probes with vLLM.

70B model deployment requiring 4x H100 GPUs.
Single service that handles all probe types (deception, hallucination, etc.)
by loading from volume paths and returning per-token activations.
"""

import modal
from typing import List, Dict, Any, Optional, Tuple
import json
from pathlib import Path
import os

# Configuration for 70B model
DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
N_GPU = 4  # 4x H100 for 70B model
GPU_CONFIG = modal.gpu.H100(count=4)
SCALEDOWN_WINDOW = 2 * 60  # 2 minutes
TIMEOUT = 30 * 60  # 30 minutes (longer for 70B)

# Volume for storing models and probes (shared with 8B service)
VOLUME = modal.Volume.from_name("unified-probe-models", create_if_missing=False)
VOLUME_PATH = "/volume"  # Mount volume at /volume, it contains models/ subdirectory
PROBES_DIR = Path(VOLUME_PATH) / "models" / "probes"
MODEL_CACHE_DIR = Path(VOLUME_PATH) / "models" / "huggingface"  # HuggingFace model cache

# Load HF token for accessing Llama models
if modal.is_local():
    from dotenv import load_dotenv
    load_dotenv()
    hf_token = os.getenv("HF_TOKEN") or os.getenv("HF_TOKEN_READ")
    if not hf_token:
        raise ValueError("HF_TOKEN or HF_TOKEN_READ must be set in environment or .env file")
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

app = modal.App("unified-probe-service-70b", image=image)


@app.function(
    image=image,
    volumes={VOLUME_PATH: VOLUME},
    secrets=[LOCAL_HF_TOKEN_SECRET],
    timeout=3600,  # 1 hour for download
)
def download_model_to_volume(model_name: str = DEFAULT_MODEL):
    """
    Download model to volume once for caching.
    
    Run this once with: modal run unified_probe_service_70b.py::download_model_to_volume
    """
    from huggingface_hub import snapshot_download
    import os
    
    cache_dir = MODEL_CACHE_DIR / model_name.replace("/", "--")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading {model_name} to {cache_dir}...")
    print(f"This will take ~10-15 minutes for 70B model (~140GB)")
    
    snapshot_download(
        repo_id=model_name,
        local_dir=str(cache_dir),
        local_dir_use_symlinks=False,
        token=os.environ.get("HF_TOKEN"),
    )
    
    # Commit volume changes
    VOLUME.commit()
    print(f"✓ Model cached at {cache_dir}")
    print(f"Volume committed. Model will be available for all future deployments.")
    
    return str(cache_dir)


def load_probe_from_volume(probe_path: Path):
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
    import torch
    import torch.nn as nn
    import pickle
    
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
    Unified Modal service for 70B probe inference.
    
    Handles all probe types via volume paths and returns per-token activations.
    """
    
    model_name: str = modal.parameter(default=DEFAULT_MODEL)
    
    # These will be initialized in load_model
    llm = None
    tokenizer = None
    loaded_probes = None
    
    @modal.enter()
    def load_model(self):
        """Load vLLM model on container startup."""
        from vllm import LLM
        from transformers import AutoTokenizer
        
        print(f"Loading vLLM 70B model: {self.model_name}")
        
        # Initialize cache
        self.loaded_probes = {}
        
        # Check if model is cached on volume
        model_cache_path = MODEL_CACHE_DIR / self.model_name.replace("/", "--")
        
        if model_cache_path.exists():
            print(f"✓ Loading from cached model at {model_cache_path}")
            model_to_load = str(model_cache_path)
            download_dir = None
        else:
            print(f"⚠ Model not cached, will download from HuggingFace")
            print(f"  Run 'modal run unified_probe_service_70b.py::download_model_to_volume' to cache the model")
            model_to_load = self.model_name
            download_dir = str(MODEL_CACHE_DIR)
        
        # Initialize vLLM with tensor parallelism for 70B
        self.llm = LLM(
            model=model_to_load,
            gpu_memory_utilization=0.90,
            max_model_len=8192,
            trust_remote_code=True,
            enforce_eager=True,  # Required for hooks
            download_dir=download_dir,
            tensor_parallel_size=N_GPU,  # 4-way tensor parallelism
        )
        
        # Load tokenizer (use cached path if available)
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_to_load,
            token=os.environ.get("HF_TOKEN")
        )
        
        print("✓ 70B Model loaded successfully!")
    
    def _load_probe_if_needed(self, probe_path: str):
        """Load probe from volume if not already cached."""
        import torch
        
        if probe_path not in self.loaded_probes:
            path = Path(probe_path)
            if not path.is_absolute():
                # Make relative paths relative to /volume/models/probes/
                path = Path("/volume/models/probes") / path
            
            probe_head, layer_idx = load_probe_from_volume(path)
            
            # Move to GPU and convert to bfloat16 to match vLLM model dtype
            probe_head = probe_head.to(device='cuda', dtype=torch.bfloat16)
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
        top_k_logits: int = 0,
    ) -> Dict[str, Any]:
        """
        Generate text with per-token probe activations (public API).
        
        This is a wrapper around _generate_with_probe_impl for external calls.
        
        Args:
            messages: Chat messages
            probe_path: Path to probe on volume
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k_logits: Number of top logits to return per token (0 = disabled)
        """
        return self._generate_with_probe_impl(
            messages=messages,
            probe_path=probe_path,
            max_tokens=max_tokens,
            temperature=temperature,
            top_k_logits=top_k_logits
        )
    
    def _generate_with_probe_impl(
        self,
        messages: List[Dict[str, str]],
        probe_path: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_k_logits: int = 10,
    ) -> Dict[str, Any]:
        """
        Internal implementation of generate_with_probe.
        Generate text with per-token probe activations.
        
        Args:
            messages: Chat messages
            probe_path: Path to probe on volume (relative to /models/probes/ or absolute)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k_logits: Number of top logits to return per token (0 = disabled)
            
        Returns:
            {
                "generated_text": str,              # Full generated text
                "generated_tokens": List[str],      # List of token strings
                "token_scores": List[float],        # Raw probe score per token (pre-sigmoid)
                "top_k_logits": List[Dict[str, float]],  # Top-k logits per token (if enabled)
                "prompt_num_tokens": int,           # Number of prompt tokens
                "generated_num_tokens": int,        # Number of generated tokens
            }
        """
        from vllm import SamplingParams, TokensPrompt
        import torch
        
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
                logprobs=top_k_logits if top_k_logits > 0 else None,
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
            
            # Extract logprobs if requested
            logits_list = None
            if top_k_logits > 0 and outputs[0].outputs[0].logprobs:
                logits_list = []
                for logprob_dict in outputs[0].outputs[0].logprobs:
                    if logprob_dict is not None:
                        # Convert token IDs to strings and logprobs to dict
                        token_logprobs = {
                            self.tokenizer.decode([token_id]): logprob.logprob
                            for token_id, logprob in logprob_dict.items()
                        }
                        logits_list.append(token_logprobs)
            
            result = {
                "generated_text": generated_text,
                "generated_tokens": generated_tokens,
                "token_scores": token_scores,
                "prompt_num_tokens": prompt_num_tokens,
                "generated_num_tokens": len(generated_ids),
            }
            
            if logits_list is not None:
                result["top_k_logits"] = logits_list
            
            return result
            
        except Exception as e:
            import traceback
            return {
                "error": f"Generation failed: {str(e)}",
                "traceback": traceback.format_exc()
            }
    
    @modal.method()
    def generate_with_probes(
        self,
        messages: List[Dict[str, str]],
        probe_paths: Dict[str, str],
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_k_logits: int = 0,
    ) -> Dict[str, Any]:
        """
        Generate text with multiple probe activations.
        
        NOTE: Currently runs generation N times (once per probe) due to complexity
        of attaching multiple hooks. With temperature > 0, text may differ slightly
        between runs. The first probe's generated text is returned.
        
        Args:
            messages: Chat messages
            probe_paths: Dict mapping probe names to volume paths
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k_logits: Number of top logits to return per token (0 = disabled)
            
        Returns:
            {
                "generated_text": str,
                "generated_tokens": List[str],
                "top_k_logits": List[Dict[str, float]],  # If enabled
                "probe_results": {
                    "probe_name1": {
                        "token_scores": List[float],
                        "prompt_num_tokens": int,
                        "generated_num_tokens": int,
                    },
                    "probe_name2": {...},
                },
            }
        """
        try:
            probe_results = {}
            generated_text = None
            generated_tokens = None
            top_k_logits_result = None
            
            # Run each probe separately
            # Note: We need to call the internal implementation directly since we can't
            # use .remote() on self methods from within the class
            for probe_name, probe_path in probe_paths.items():
                # Call the internal implementation directly
                probe_result = self._generate_with_probe_impl(
                    messages=messages,
                    probe_path=probe_path,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_k_logits=top_k_logits,
                )
                
                if "error" in probe_result:
                    return {"error": f"Probe {probe_name} failed: {probe_result['error']}"}
                
                # Store probe-specific results
                probe_results[probe_name] = {
                    "token_scores": probe_result["token_scores"],
                    "prompt_num_tokens": probe_result["prompt_num_tokens"],
                    "generated_num_tokens": probe_result["generated_num_tokens"],
                }
                
                # Use text/tokens/logits from first probe
                if generated_text is None:
                    generated_text = probe_result["generated_text"]
                    generated_tokens = probe_result["generated_tokens"]
                    top_k_logits_result = probe_result.get("top_k_logits")
            
            result = {
                "generated_text": generated_text,
                "generated_tokens": generated_tokens,
                "probe_results": probe_results,
            }
            
            if top_k_logits_result is not None:
                result["top_k_logits"] = top_k_logits_result
            
            return result
            
        except Exception as e:
            import traceback
            return {
                "error": f"Multi-probe generation failed: {str(e)}",
                "traceback": traceback.format_exc()
            }
    
    @modal.method()
    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Generate without probe scoring (faster). Alias for backward compatibility."""
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


@app.function(image=image, volumes={VOLUME_PATH: VOLUME})
def health_check():
    """Health check endpoint."""
    import os
    from pathlib import Path
    
    # Check what's in the volume
    probes_dir = Path("/volume/models/probes")
    if probes_dir.exists():
        probe_files = {}
        for item in probes_dir.iterdir():
            if item.is_dir():
                probe_files[str(item)] = list(str(f) for f in item.iterdir())
        return {"status": "healthy", "service": "unified-probe-service-70b", "probes": probe_files}
    else:
        # Check what's at volume root for debugging
        vol_root = Path("/volume")
        if vol_root.exists():
            root_contents = list(str(f) for f in vol_root.iterdir())
            return {"status": "healthy", "service": "unified-probe-service-70b", "error": "probes not found", "volume_root": root_contents}
        else:
            return {"status": "healthy", "service": "unified-probe-service-70b", "error": "/volume not mounted"}


if __name__ == "__main__":
    # Test locally
    with app.run():
        service = UnifiedProbeService()
        
        result = service.generate_with_probe.remote(
            messages=[{"role": "user", "content": "What is 2+2?"}],
            probe_path="deception_70b_layer30",  # Example path for 70B
            max_tokens=50
        )
        
        print(result)
