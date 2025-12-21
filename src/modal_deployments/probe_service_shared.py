"""
Shared code for Modal probe services (8B and 70B).

This module contains common functionality used by both unified_probe_service.py
and unified_probe_service_70b.py to reduce code duplication.
"""

import json
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


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
    import pickle

    import torch
    import torch.nn as nn

    # Check for Apollo format first (.pt file)
    apollo_file = probe_path / "probe_detector.pt"
    if apollo_file.exists():
        logger.info(f"Loading Apollo format probe from {probe_path}")
        with open(apollo_file, "rb") as f:
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
        direction = (
            directions[layer_idx] if isinstance(directions, dict) else directions
        )

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
        logger.info(f"Loading hallucination format probe from {probe_path}")

        # Load config
        with open(config_file) as f:
            config = json.load(f)

        hidden_size = config["hidden_size"]
        layer_idx = config["layer_idx"]

        # Create probe head
        probe_head = nn.Linear(hidden_size, 1, device="cpu", dtype=torch.float32)

        # Load weights
        state_dict = torch.load(weights_file, map_location="cpu", weights_only=True)
        probe_head.load_state_dict(state_dict)
        probe_head.eval()

        return probe_head, layer_idx

    raise ValueError(
        f"No valid probe found at {probe_path}. Expected probe_detector.pt or probe_head.bin+probe_config.json"
    )


def load_probe_if_needed(probe_path: str, loaded_probes: dict):
    """
    Load probe from volume if not already cached.

    Args:
        probe_path: Path to probe directory. Can be:
            - Absolute path (e.g., "/volume/models/probes/deception_8b_layer12")
            - Relative to /volume/models/probes/ (e.g., "deception_8b_layer12")
        loaded_probes: Dictionary of already loaded probes to check/update

    Returns:
        (probe_head, layer_idx): The probe head module and target layer index

    Note: Relative paths are ALWAYS relative to /volume/models/probes/, not /volume/models/.
    So "deception_8b" becomes "/volume/models/probes/deception_8b", not "/volume/models/deception_8b".
    """
    import torch

    if probe_path not in loaded_probes:
        path = Path(probe_path)
        if not path.is_absolute():
            # Make relative paths relative to /volume/models/probes/
            path = Path("/volume/models/probes") / path

        probe_head, layer_idx = load_probe_from_volume(path)

        # Move to GPU and convert to bfloat16 to match vLLM model dtype
        probe_head = probe_head.to(device="cuda", dtype=torch.bfloat16)
        probe_head.eval()

        loaded_probes[probe_path] = (probe_head, layer_idx)
        logger.info(f"Loaded probe from {path} (layer {layer_idx})")

    return loaded_probes[probe_path]


def build_health_check_response(service_name: str):
    """
    Build health check response by inspecting volume contents.

    Args:
        service_name: Name of the service for the response

    Returns:
        Dict with health status and probe/volume information
    """
    from pathlib import Path

    # Check what's in the volume
    probes_dir = Path("/volume/models/probes")
    if probes_dir.exists():
        probe_files = {}
        for item in probes_dir.iterdir():
            if item.is_dir():
                probe_files[str(item)] = list(str(f) for f in item.iterdir())
        return {
            "status": "healthy",
            "service": service_name,
            "probes": probe_files,
        }
    else:
        # Check what's at volume root for debugging
        vol_root = Path("/volume")
        if vol_root.exists():
            root_contents = list(str(f) for f in vol_root.iterdir())
            return {
                "status": "healthy",
                "service": service_name,
                "error": "probes not found",
                "volume_root": root_contents,
            }
        else:
            return {
                "status": "healthy",
                "service": service_name,
                "error": "/volume not mounted",
            }


class ProbeServiceBase:
    """
    Base class for unified probe services.

    Contains all shared logic for probe inference with vLLM.
    Subclasses configure model-specific parameters (model name, GPU type, etc.)
    """

    # Subclasses must set these
    model_name: str = None
    n_gpu: int = None
    volume_path: str = "/volume"

    # These will be initialized in load_model
    llm = None
    tokenizer = None
    loaded_probes = None

    def load_model(self):
        """Load vLLM model on container startup."""
        import os
        from pathlib import Path

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
            download_dir=str(Path(self.volume_path) / "models"),
            tensor_parallel_size=self.n_gpu,
        )

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, token=os.environ.get("HF_TOKEN")
        )

        logger.info("Model loaded successfully!")

    def _load_probe_if_needed(self, probe_path: str):
        """Load probe from volume if not already cached."""
        return load_probe_if_needed(probe_path, self.loaded_probes)

    def _generate_with_probe_impl(
        self,
        messages,
        probe_path: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_k_logits: int = 10,
    ):
        """
        Internal implementation of generate_with_probe.
        Generate text with per-token probe activations.

        Args:
            messages: Chat messages
            probe_path: Path to probe on volume
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k_logits: Number of top logits to return per token (0 = disabled)

        Returns:
            Dict with generated_text, tokens, scores, etc.
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
            total_tokens = prompt_num_tokens + len(generated_ids)

            # Validate we got the expected number of scores - NO TOLERANCE
            if len(token_scores) != total_tokens:
                raise ValueError(
                    f"Probe hook captured {len(token_scores)} scores but expected {total_tokens}. "
                    f"prompt_token_ids: {len(prompt_token_ids)}, generated_ids: {len(generated_ids)}. "
                    f"This is a bug - investigate why the hook didn't fire for all tokens."
                )

            # Split into prompt and generation scores
            prompt_token_scores = token_scores[:prompt_num_tokens]
            generation_token_scores = token_scores[prompt_num_tokens:]

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
                "token_scores": generation_token_scores,
                "prompt_tokens": prompt_tokens,
                "prompt_token_scores": prompt_token_scores,
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

    def _generate_with_probes_impl(
        self,
        messages,
        probe_paths,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_k_logits: int = 0,
    ):
        """
        Generate text with multiple probe activations in a SINGLE generation run.

        Args:
            messages: Chat messages
            probe_paths: Dict mapping probe names to volume paths
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k_logits: Number of top logits to return per token (0 = disabled)

        Returns:
            Dict with generated_text, tokens, and probe_results
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

            # Storage for each probe's scores
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
            total_tokens = prompt_num_tokens + len(generated_ids)

            # Storage for split scores
            probe_generation_scores = {}
            probe_prompt_scores = {}

            for probe_name in probe_paths:
                token_scores = probe_token_scores[probe_name]

                # Validate we got the expected number of scores - NO TOLERANCE
                if len(token_scores) != total_tokens:
                    raise ValueError(
                        f"Probe '{probe_name}' hook captured {len(token_scores)} scores but expected {total_tokens}. "
                        f"prompt_token_ids: {len(prompt_token_ids)}, generated_ids: {len(generated_ids)}. "
                        f"This is a bug - investigate why the hook didn't fire for all tokens."
                    )

                # Split into prompt and generation scores
                probe_prompt_scores[probe_name] = token_scores[:prompt_num_tokens]
                probe_generation_scores[probe_name] = token_scores[prompt_num_tokens:]

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
                    "token_scores": probe_generation_scores[probe_name],
                    "prompt_token_scores": probe_prompt_scores[probe_name],
                    "prompt_num_tokens": prompt_num_tokens,
                    "generated_num_tokens": len(generated_ids),
                }

            result = {
                "generated_text": generated_text,
                "generated_tokens": generated_tokens,
                "prompt_tokens": prompt_tokens,
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

    def _generate_impl(
        self,
        messages,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ):
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
