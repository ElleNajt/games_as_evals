"""
Experiment-level configuration that can be applied across different games.

This allows you to define probe/model settings once and apply them consistently
to Werewolf, TTL, or any other game.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ExperimentConfig:
    """
    High-level experiment configuration for probe/model settings.

    Define this once and apply to any game to ensure consistent settings.
    """

    # Model configuration
    model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    """Model to use for all players"""

    # Probe configuration
    probes: List[str] = None
    """List of probes to apply (e.g., ["deception_8b", "hallucination_8b"])"""

    # Logging/observability
    top_k_logits: int = 10
    """Number of top-k logits to extract (0 = disabled)"""

    # Backend
    backend_type: str = "modal"
    """Backend type (modal, claude, openrouter)"""

    # Generation parameters
    temperature: float = 0.7
    """Default temperature for generation"""

    max_tokens: int = 512
    """Default max tokens for generation"""

    # Experiment metadata
    experiment_name: str = "experiment"
    """Base name for this experiment"""

    description: str = ""
    """Human-readable description of this experiment"""

    def __post_init__(self):
        """Initialize probes to empty list if None."""
        if self.probes is None:
            self.probes = []

    def to_player_config_kwargs(
        self, player_name: str = "Player", system_prompt: str = ""
    ) -> dict:
        """
        Convert to kwargs for PlayerConfig.

        Args:
            player_name: Name for the player
            system_prompt: System prompt for the player

        Returns:
            Dict of kwargs to pass to PlayerConfig()

        Example:
            >>> exp = ExperimentConfig(model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            ...                        probes=["deception_8b", "hallucination_8b"])
            >>> player_cfg = PlayerConfig(**exp.to_player_config_kwargs("Alice", "You are Alice"))
        """
        from .player_config import PlayerConfig

        kwargs = {
            "name": player_name,
            "backend_type": self.backend_type,
            "model": self.model,
            "system_prompt": system_prompt,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # Handle probes - NOTE: top_k_logits is NOT included here
        # It's a backend-level parameter, not a PlayerConfig parameter
        if self.probes:
            kwargs["probes"] = self.probes

        return kwargs


# Predefined experiment configs for common setups
def get_experiment_config(preset: str) -> ExperimentConfig:
    """
    Get predefined experiment configuration.

    Args:
        preset: Preset name (8b_both, 70b_both, 8b_deception, etc.)

    Returns:
        ExperimentConfig instance

    Available presets:
        - 8b_both: 8B model with deception + hallucination probes
        - 8b_both_massmean: 8B model with massmean deception probe (78% val) + hallucination probe
        - 70b_both: 70B model with deception + hallucination probes
        - 8b_deception: 8B model with deception probe only
        - 8b_hallucination: 8B model with hallucination probe only
        - 70b_deception: 70B model with deception probe only
        - 70b_hallucination: 70B model with hallucination probe only
        - baseline_8b: 8B model with no probes
        - baseline_70b: 70B model with no probes

    Example:
        >>> from src.experiments.ttl.configs import create_ttl_config
        >>> from src.experiments.werewolf.configs import create_werewolf_config
        >>> exp = get_experiment_config("8b_both")
        >>> ttl_cfg = create_ttl_config(exp)
        >>> werewolf_cfg = create_werewolf_config(exp, num_players=6)
    """
    presets = {
        "8b_both": ExperimentConfig(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            probes=["deception_8b", "hallucination_8b"],
            top_k_logits=10,
            description="8B model with both deception and hallucination probes",
        ),
        "8b_both_massmean": ExperimentConfig(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            probes=["deception_8b_massmean", "hallucination_8b"],
            top_k_logits=10,
            description="8B model with massmean deception probe (78% val acc) and hallucination probe",
        ),
        "70b_both": ExperimentConfig(
            model="meta-llama/Llama-3.3-70B-Instruct",
            probes=["deception_70b", "hallucination_70b"],
            top_k_logits=10,
            description="70B model with both deception and hallucination probes",
        ),
        "8b_deception": ExperimentConfig(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            probes=["deception_8b"],
            top_k_logits=10,
            description="8B model with deception probe only",
        ),
        "8b_hallucination": ExperimentConfig(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            probes=["hallucination_8b"],
            top_k_logits=10,
            description="8B model with hallucination probe only",
        ),
        "70b_deception": ExperimentConfig(
            model="meta-llama/Llama-3.3-70B-Instruct",
            probes=["deception_70b"],
            top_k_logits=10,
            description="70B model with deception probe only",
        ),
        "70b_hallucination": ExperimentConfig(
            model="meta-llama/Llama-3.3-70B-Instruct",
            probes=["hallucination_70b"],
            top_k_logits=10,
            description="70B model with hallucination probe only",
        ),
        "baseline_8b": ExperimentConfig(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            probes=[],
            top_k_logits=10,
            description="8B model baseline (no probes)",
        ),
        "baseline_70b": ExperimentConfig(
            model="meta-llama/Llama-3.3-70B-Instruct",
            probes=[],
            top_k_logits=10,
            description="70B model baseline (no probes)",
        ),
    }

    if preset not in presets:
        available = ", ".join(presets.keys())
        raise ValueError(f"Unknown preset '{preset}'. Available: {available}")

    return presets[preset]
