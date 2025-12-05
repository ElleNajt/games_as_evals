"""Modal backend implementation with multi-probe support."""

import logging
import math
from typing import Any, Dict, List, Optional

import modal

from ..probes.registry import PROBE_REGISTRY, get_probe_config
from .base import GenerationResult, LLMBackend, ProbeScoreData, ProbeScores

logger = logging.getLogger(__name__)


def sigmoid(x: float) -> float:
    """Apply sigmoid transformation to convert logits to probabilities."""
    return 1 / (1 + math.exp(-x))


class ModalBackend(LLMBackend):
    """
    Backend using Modal for generation with optional probe scoring.

    Supports multiple probes running simultaneously.
    Connects to unified-probe-service Modal deployment.
    """

    def __init__(
        self,
        probes: Optional[List[str]] = None,
        modal_app_name: Optional[str] = None,
        top_k_logits: int = 0,
        **kwargs,
    ):
        """
        Initialize Modal backend.

        Args:
            probes: List of probe names (e.g., ["deception_8b", "hallucination_8b"])
            modal_app_name: Override Modal app name (defaults to probe config)
            top_k_logits: Number of top logits to return per token (0 = disabled)
            **kwargs: Additional config (unused for now)
        """
        self.probe_names = probes or []
        self.top_k_logits = top_k_logits

        # Get configs for all probes
        self.probe_configs = {}
        if self.probe_names:
            for probe_name in self.probe_names:
                self.probe_configs[probe_name] = get_probe_config(probe_name)

        # Validate all probes use same model and app
        if self.probe_configs:
            models = set(cfg.model_name for cfg in self.probe_configs.values())
            if len(models) > 1:
                raise ValueError(
                    f"All probes must be for the same model. Got probes for: {models}. "
                    f"Cannot mix 8B and 70B probes in a single backend."
                )

            apps = set(cfg.modal_app_name for cfg in self.probe_configs.values())
            if len(apps) > 1:
                raise ValueError(f"All probes must use same Modal app, got: {apps}")

            if not modal_app_name:
                modal_app_name = list(apps)[0]

        self.modal_app_name = modal_app_name or "unified-probe-service"
        self.service = None

        probe_str = ", ".join(self.probe_names) if self.probe_names else "none"
        logits_str = f", top_k={top_k_logits}" if top_k_logits > 0 else ""
        logger.info(
            f"ModalBackend initialized (app={self.modal_app_name}, probes=[{probe_str}]{logits_str})"
        )

    def _ensure_connected(self):
        """Lazy connect to Modal service."""
        if self.service is None:
            logger.info(f"Connecting to Modal app '{self.modal_app_name}'...")
            cls = modal.Cls.from_name(self.modal_app_name, "UnifiedProbeService")
            self.service = cls()
            logger.info(f"Connected to UnifiedProbeService!")

    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """
        Generate using Modal with optional probe scoring.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            GenerationResult with text, tokens, and probe_scores (if probes enabled)
        """
        self._ensure_connected()

        if self.probe_configs:
            result = self._generate_with_probes(messages, max_tokens, temperature)
        else:
            result = self._generate_without_probes(messages, max_tokens, temperature)

        return result

    def _generate_with_probes(
        self, messages: List[Dict[str, str]], max_tokens: int, temperature: float
    ) -> GenerationResult:
        """Generate with probe scoring enabled (one or more probes)."""
        # Build probe paths dict
        probe_paths = {
            name: config.volume_path for name, config in self.probe_configs.items()
        }

        # Call unified service with multiple probes
        result = self.service.generate_with_probes.remote(
            messages=messages,
            probe_paths=probe_paths,
            max_tokens=max_tokens,
            temperature=temperature,
            top_k_logits=self.top_k_logits,
        )

        if "error" in result:
            raise RuntimeError(f"Modal generation failed: {result['error']}")

        text = result["generated_text"]  # Fail if missing
        tokens = result.get("generated_tokens")
        prompt_tokens = result.get("prompt_tokens")
        top_k_logits = result.get("top_k_logits")

        # Extract probe scores for each probe
        probe_scores = None
        if "probe_results" in result:
            probe_score_dict = {}

            for probe_name, probe_data in result["probe_results"].items():
                raw_token_scores = probe_data.get("token_scores", [])
                raw_prompt_token_scores = probe_data.get("prompt_token_scores", [])

                # Get bias from probe config
                bias = self.probe_configs[probe_name].bias

                # Apply sigmoid transformation with bias to generation tokens
                token_scores = [sigmoid(score + bias) for score in raw_token_scores]

                # Apply sigmoid transformation to prompt tokens
                prompt_token_scores = [
                    sigmoid(score + bias) for score in raw_prompt_token_scores
                ]

                # Calculate aggregate (only for generation tokens)
                if not token_scores:
                    raise ValueError(f"Probe {probe_name} returned no token scores")
                aggregate = sum(token_scores) / len(token_scores)

                metadata = {
                    "num_tokens": len(token_scores),
                    "num_prompt_tokens": len(prompt_token_scores),
                    "probe_type": self.probe_configs[probe_name].probe_type,
                    "layer": self.probe_configs[probe_name].layer,
                }

                probe_score_dict[probe_name] = ProbeScoreData(
                    aggregate_score=aggregate,
                    token_scores=token_scores,
                    prompt_token_scores=prompt_token_scores,  # NEW: Include prompt scores
                    phase_scores=None,
                    metadata=metadata,
                )

            probe_scores = ProbeScores(scores=probe_score_dict)

        return GenerationResult(
            text=text,
            tokens=tokens,
            prompt_tokens=prompt_tokens,  # NEW: Include prompt tokens
            top_k_logits=top_k_logits,
            probe_scores=probe_scores,
        )

    def _generate_without_probes(
        self, messages: List[Dict[str, str]], max_tokens: int, temperature: float
    ) -> GenerationResult:
        """Generate without probe scoring."""
        result = self.service.generate.remote(
            messages=messages, max_tokens=max_tokens, temperature=temperature
        )

        if "error" in result:
            raise RuntimeError(f"Modal generation failed: {result['error']}")

        text = result["generated_text"]  # Fail if missing
        tokens = result.get("tokens")

        return GenerationResult(
            text=text, tokens=tokens, top_k_logits=None, probe_scores=None
        )

    @property
    def supports_probes(self) -> bool:
        return len(self.probe_configs) > 0

    @property
    def supports_logits(self) -> bool:
        return self.top_k_logits > 0
