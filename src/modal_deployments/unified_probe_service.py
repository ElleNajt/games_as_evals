"""
Unified Modal backend for serving LLM probes with vLLM.

Single service that handles all probe types (deception, hallucination, etc.)
by loading from volume paths and returning per-token activations.

Version: 2.2 - DRY refactoring, extracted shared code (2025-12-05)
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import modal

from .probe_service_shared import (
    build_health_check_response,
    load_probe_from_volume,
    load_probe_if_needed,
)

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"
N_GPU = 1  # Default to 1 GPU (A10G for 8B models)
GPU_CONFIG = "A10G"
SCALEDOWN_WINDOW = 2 * 60  # 2 minutes
TIMEOUT = 20 * 60  # 20 minutes

# Volume for storing models and probes
VOLUME = modal.Volume.from_name("unified-probe-models", create_if_missing=False)
VOLUME_PATH = "/volume"  # Mount volume at /volume, it contains models/ subdirectory
PROBES_DIR = Path(VOLUME_PATH) / "models" / "probes"

# Use existing Modal secret for HuggingFace token
# Secret should be named "huggingface-secret" in your Modal account
HF_SECRET = modal.Secret.from_name("huggingface-secret")

# Modal image
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch>=2.0.0",
    "transformers>=4.40.0",
    "accelerate>=0.20.0",
    "numpy>=1.24.0",
    "vllm==0.6.3",  # Pin to 0.6.3 for stability
    "huggingface_hub>=0.20.0",
    "scikit-learn>=1.3.0",  # For probe loaders
    "jaxtyping>=0.2.0",
)

app = modal.App("unified-probe-service", image=image)


@app.cls(
    image=image,
    gpu=GPU_CONFIG,
    container_idle_timeout=SCALEDOWN_WINDOW,
    volumes={VOLUME_PATH: VOLUME},
    timeout=TIMEOUT,
    secrets=[HF_SECRET],
)
class UnifiedProbeService:
    """
    Unified Modal service for probe inference.

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
        from transformers import AutoTokenizer
        from vllm import LLM

        logger.info(f"Loading vLLM model: {self.model_name}")

        # Initialize cache
        self.loaded_probes = {}

        # Initialize vLLM
        self.llm = LLM(
            model=self.model_name,
            gpu_memory_utilization=0.90,
            max_model_len=8192,
            trust_remote_code=True,
            enforce_eager=True,  # Required for hooks
            download_dir=str(Path(VOLUME_PATH) / "models"),
            tensor_parallel_size=N_GPU,
        )

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, token=os.environ.get("HF_TOKEN")
        )

        logger.info("Model loaded successfully!")

    def _load_probe_if_needed(self, probe_path: str):
        """Load probe from volume if not already cached (delegates to shared function)."""
        return load_probe_if_needed(probe_path, self.loaded_probes)

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
            top_k_logits=top_k_logits,
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
        import torch
        from vllm import SamplingParams, TokensPrompt

        try:
            # Load probe
            probe_head, probe_layer = self._load_probe_if_needed(probe_path)

            # Format conversation
            prompt_token_ids = self.tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True
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

            # Storage for probe scores (both prompt and generated tokens)
            token_scores = []

            def activation_hook(module, input, output):
                """Capture activations and score them."""
                nonlocal token_scores

                # Extract hidden states
                assert len(output) == 2
                hidden_states, residual = output
                resid_post = hidden_states + residual

                # Score with probe (keep on GPU)
                with torch.no_grad():
                    scores = probe_head(resid_post).squeeze(-1)

                    # Handle batched or sequential processing
                    if scores.dim() == 0:
                        # Single token
                        token_scores.append(scores.item())
                    else:
                        # Multiple tokens in batch - append all scores
                        token_scores.extend(scores.tolist())

            # Register hook
            hook_handle = target_layer.register_forward_hook(activation_hook)

            try:
                # Generate
                outputs = self.llm.generate(
                    prompts=[TokensPrompt(prompt_token_ids=prompt_token_ids)],
                    sampling_params=sampling_params,
                    use_tqdm=False,
                )

                # Extract tokens
                generated_ids = list(outputs[0].outputs[0].token_ids)

            finally:
                hook_handle.remove()

            # Separate prompt scores from generation scores
            # token_scores now contains scores for ALL tokens (prompt + generation)
            total_tokens = prompt_num_tokens + len(generated_ids)

            # Validate we got the expected number of scores (allow 1-2 token tolerance for special tokens)
            tolerance = 2
            if abs(len(token_scores) - total_tokens) > tolerance:
                raise ValueError(
                    f"Probe hook captured {len(token_scores)} scores but expected {total_tokens} "
                    f"({prompt_num_tokens} prompt + {len(generated_ids)} generated). "
                    f"Difference of {abs(len(token_scores) - total_tokens)} exceeds tolerance of {tolerance}. "
                    f"This indicates the hook didn't fire for all tokens."
                )

            # Split into prompt and generation scores
            # If we have fewer scores than expected (due to special tokens), adjust split
            actual_num_scores = len(token_scores)
            if actual_num_scores < total_tokens:
                # Missing tokens likely at the end (EOS), keep prompt split the same
                prompt_token_scores = token_scores[:min(prompt_num_tokens, actual_num_scores)]
                generation_token_scores = token_scores[min(prompt_num_tokens, actual_num_scores):]
            else:
                # Normal case or extra scores
                prompt_token_scores = token_scores[:prompt_num_tokens]
                generation_token_scores = token_scores[prompt_num_tokens:total_tokens]

            # Decode ALL tokens (prompt + generation)
            prompt_tokens = self.tokenizer.convert_ids_to_tokens(prompt_token_ids)
            generated_tokens = self.tokenizer.convert_ids_to_tokens(generated_ids)
            generated_text = self.tokenizer.decode(
                generated_ids, skip_special_tokens=True
            )

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
                "token_scores": generation_token_scores,  # Generation token scores
                "prompt_tokens": prompt_tokens,  # NEW: Prompt tokens
                "prompt_token_scores": prompt_token_scores,  # NEW: Prompt token scores
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
                "traceback": traceback.format_exc(),
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
        Generate text with multiple probe activations in a SINGLE generation run.

        This method registers multiple forward hooks (one per probe) and runs
        generation ONCE. All probes score the same generated tokens.

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
        import torch
        from vllm import SamplingParams, TokensPrompt

        try:
            # Load all probe heads and their target layers
            probe_heads = {}
            probe_layers = {}
            for probe_name, probe_path in probe_paths.items():
                probe_head, probe_layer = self._load_probe_if_needed(probe_path)
                probe_heads[probe_name] = probe_head
                probe_layers[probe_name] = probe_layer

            # Format conversation
            prompt_token_ids = self.tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True
            )
            prompt_num_tokens = len(prompt_token_ids)

            # Sampling parameters
            sampling_params = SamplingParams(
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9 if temperature > 0 else 1.0,
                logprobs=top_k_logits if top_k_logits > 0 else None,
            )

            # Get model
            model = self.llm.llm_engine.model_executor.driver_worker.model_runner.model

            # Storage for each probe's scores (both prompt and generated tokens)
            probe_token_scores = {probe_name: [] for probe_name in probe_paths}

            # Create activation hooks for each probe
            hook_handles = []

            for probe_name, probe_layer in probe_layers.items():
                probe_head = probe_heads[probe_name]
                target_layer = model.model.layers[probe_layer]

                # Create closure that captures probe_name, probe_head
                def make_hook(pname, phead):
                    def activation_hook(module, input, output):
                        """Capture activations and score them."""
                        nonlocal probe_token_scores

                        # Extract hidden states
                        assert len(output) == 2
                        hidden_states, residual = output
                        resid_post = hidden_states + residual

                        # Score with probe (keep on GPU)
                        with torch.no_grad():
                            scores = phead(resid_post).squeeze(-1)

                            # Handle batched or sequential processing
                            if scores.dim() == 0:
                                # Single token
                                probe_token_scores[pname].append(scores.item())
                            else:
                                # Multiple tokens in batch - append all scores
                                probe_token_scores[pname].extend(scores.tolist())

                    return activation_hook

                # Register hook for this probe
                hook = make_hook(probe_name, probe_head)
                hook_handle = target_layer.register_forward_hook(hook)
                hook_handles.append(hook_handle)

            try:
                # Generate ONCE with all hooks active
                outputs = self.llm.generate(
                    prompts=[TokensPrompt(prompt_token_ids=prompt_token_ids)],
                    sampling_params=sampling_params,
                    use_tqdm=False,
                )

                # Extract tokens
                generated_ids = list(outputs[0].outputs[0].token_ids)

            finally:
                # Remove all hooks
                for hook_handle in hook_handles:
                    hook_handle.remove()

            # Separate prompt scores from generation scores for each probe
            # Each probe's token_scores now contains scores for ALL tokens (prompt + generation)
            total_tokens = prompt_num_tokens + len(generated_ids)

            # Storage for split scores
            probe_generation_scores = {}
            probe_prompt_scores = {}

            for probe_name in probe_paths:
                token_scores = probe_token_scores[probe_name]

                # Validate we got the expected number of scores (allow 1-2 token tolerance for special tokens)
                tolerance = 2
                if abs(len(token_scores) - total_tokens) > tolerance:
                    raise ValueError(
                        f"Probe '{probe_name}' hook captured {len(token_scores)} scores but expected {total_tokens} "
                        f"({prompt_num_tokens} prompt + {len(generated_ids)} generated). "
                        f"Difference of {abs(len(token_scores) - total_tokens)} exceeds tolerance of {tolerance}. "
                        f"This indicates the hook didn't fire for all tokens."
                    )

                # Split into prompt and generation scores
                # If we have fewer scores than expected (due to special tokens), adjust split
                actual_num_scores = len(token_scores)
                if actual_num_scores < total_tokens:
                    # Missing tokens likely at the end (EOS), keep prompt split the same
                    probe_prompt_scores[probe_name] = token_scores[:min(prompt_num_tokens, actual_num_scores)]
                    probe_generation_scores[probe_name] = token_scores[min(prompt_num_tokens, actual_num_scores):]
                else:
                    # Normal case or extra scores
                    probe_prompt_scores[probe_name] = token_scores[:prompt_num_tokens]
                    probe_generation_scores[probe_name] = token_scores[prompt_num_tokens:total_tokens]

            # Decode ALL tokens (prompt + generation)
            prompt_tokens = self.tokenizer.convert_ids_to_tokens(prompt_token_ids)
            generated_tokens = self.tokenizer.convert_ids_to_tokens(generated_ids)
            generated_text = self.tokenizer.decode(
                generated_ids, skip_special_tokens=True
            )

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

            # Build probe results
            probe_results = {}
            for probe_name in probe_paths:
                probe_results[probe_name] = {
                    "token_scores": probe_generation_scores[
                        probe_name
                    ],  # Generation token scores
                    "prompt_token_scores": probe_prompt_scores[
                        probe_name
                    ],  # NEW: Prompt token scores
                    "prompt_num_tokens": prompt_num_tokens,
                    "generated_num_tokens": len(generated_ids),
                }

            result = {
                "generated_text": generated_text,
                "generated_tokens": generated_tokens,
                "prompt_tokens": prompt_tokens,  # NEW: Prompt tokens
                "probe_results": probe_results,
            }

            if logits_list is not None:
                result["top_k_logits"] = logits_list

            return result

        except Exception as e:
            import traceback

            return {
                "error": f"Multi-probe generation failed: {str(e)}",
                "traceback": traceback.format_exc(),
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
                messages, tokenize=False, add_generation_prompt=True
            )

            # Generate
            outputs = self.llm.generate(
                prompts=[prompt], sampling_params=sampling_params, use_tqdm=False
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
        """Generate without probe scoring (faster). Alias for backward compatibility."""
        return self.generate(messages, max_tokens, temperature)


@app.function(image=image, volumes={VOLUME_PATH: VOLUME})
def health_check():
    """Health check endpoint."""
    return build_health_check_response("unified-probe-service")


if __name__ == "__main__":
    # Test locally
    with app.run():
        service = UnifiedProbeService()

        result = service.generate_with_probe.remote(
            messages=[{"role": "user", "content": "What is 2+2?"}],
            probe_path="deception_8b_layer12",  # Example path
            max_tokens=50,
        )

        print(result)
