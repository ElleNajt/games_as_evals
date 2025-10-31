"""Modal backend implementation with probe support."""

import math
from typing import Any, Dict, List, Optional

import modal

from ..probes.registry import get_probe_config
from .base import GenerationResult, LLMBackend, ProbeScores


def sigmoid(x: float) -> float:
    """Apply sigmoid transformation to convert logits to probabilities."""
    return 1 / (1 + math.exp(-x))


class ModalBackend(LLMBackend):
    """
    Backend using Modal for generation with optional probe scoring.

    Supports probes, tokens, and optionally logits.
    Connects to existing Modal deployments (werewolf-apollo-probe, etc.)
    """

    def __init__(
        self,
        probe: Optional[str] = None,
        modal_app_name: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize Modal backend.

        Args:
            probe: Probe name from registry (e.g., "deception_8b", "hallucination_8b")
                  If None, no probe scoring is performed.
            modal_app_name: Override Modal app name (defaults to probe config)
            **kwargs: Additional config (unused for now)
        """
        self.probe_name = probe
        self.probe_config = get_probe_config(probe) if probe else None
        self.modal_app_name = modal_app_name or (
            self.probe_config.modal_app_name if self.probe_config else None
        )
        self.service = None

        if not self.modal_app_name:
            raise ValueError(
                "modal_app_name must be provided if probe is None. "
                "Either specify probe (e.g., 'deception_8b') or modal_app_name."
            )

        print(f"ModalBackend initialized (app={self.modal_app_name}, probe={probe})")

    def _ensure_connected(self):
        """Lazy connect to Modal service."""
        if self.service is None:
            print(f"Connecting to Modal app '{self.modal_app_name}'...")

            # All probes now use UnifiedProbeService
            cls = modal.Cls.from_name(self.modal_app_name, "UnifiedProbeService")
            self.service = cls()

            print(f"Connected to UnifiedProbeService!")

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
            GenerationResult with text, tokens, and probe_scores (if probe enabled)
        """
        self._ensure_connected()

        # Choose generation method based on whether probe is enabled
        if self.probe_config:
            # Generate with probe scoring
            result = self._generate_with_probe(messages, max_tokens, temperature)
        else:
            # Standard generation without probe
            result = self._generate_without_probe(messages, max_tokens, temperature)

        return result

    def _generate_with_probe(
        self, messages: List[Dict[str, str]], max_tokens: int, temperature: float
    ) -> GenerationResult:
        """Generate with probe scoring enabled."""
        # Unified interface: all probes use same method with volume path
        result = self.service.generate_with_probe.remote(
            messages=messages,
            probe_path=self.probe_config.volume_path,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if "error" in result:
            raise RuntimeError(f"Modal generation failed: {result['error']}")

        # Extract text
        text = result.get("generated_text", "")

        # Extract probe scores (unified format)
        probe_scores = None
        if "token_scores" in result:
            raw_token_scores = result["token_scores"]

            # Apply sigmoid transformation to convert logits to probabilities
            # UnifiedProbeService returns raw probe scores (can be large negative values for Apollo)
            # We convert to [0, 1] probabilities for consistent interpretation
            token_scores = [sigmoid(score) for score in raw_token_scores]

            # Calculate aggregate score as mean probability
            aggregate = sum(token_scores) / len(token_scores) if token_scores else 0.0

            metadata = {
                "num_tokens": result.get("generated_num_tokens", len(token_scores)),
                "prompt_num_tokens": result.get("prompt_num_tokens", 0),
                "probe_type": self.probe_config.probe_type
                if self.probe_config
                else "unknown",
            }

            probe_scores = ProbeScores(
                aggregate_score=aggregate,
                token_scores=token_scores,
                phase_scores=None,  # Games can compute phase scores from token_scores if needed
                metadata=metadata,
            )

        # Extract tokens
        tokens = result.get("generated_tokens")

        return GenerationResult(
            text=text,
            tokens=tokens,
            top_k_logits=None,  # Not currently extracted
            probe_scores=probe_scores,
        )

    def _generate_without_probe(
        self, messages: List[Dict[str, str]], max_tokens: int, temperature: float
    ) -> GenerationResult:
        """Generate without probe scoring."""
        result = self.service.generate.remote(
            messages=messages, max_tokens=max_tokens, temperature=temperature
        )

        if "error" in result:
            raise RuntimeError(f"Modal generation failed: {result['error']}")

        text = result.get("generated_text") or result.get("text", "")
        tokens = result.get("tokens")

        return GenerationResult(
            text=text, tokens=tokens, top_k_logits=None, probe_scores=None
        )

    @property
    def supports_probes(self) -> bool:
        return self.probe_config is not None

    @property
    def supports_logits(self) -> bool:
        return False  # Not currently implemented
