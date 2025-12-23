"""Player configuration for games."""

from dataclasses import dataclass, field
from typing import Optional, List, Union


@dataclass
class PlayerConfig:
    """Configuration for a single player.
    
    Each player can have different backend, model, and probe settings.
    
    Attributes:
        name: Player name/identifier
        backend_type: Backend to use (claude, openrouter, modal)
        model: Model identifier (e.g., claude-3-5-sonnet-20241022, gpt-4, llama-3.1-8b)
        probe: Optional single probe to use (deception_8b, deception_70b, hallucination_8b)
        probes: Optional list of probes to use simultaneously
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        system_prompt: System prompt for the player
        
    Note:
        Either probe or probes can be specified, but not both.
        If probe is specified, it will be converted to a single-element probes list.
    """
    
    name: str
    backend_type: str  # claude, openrouter, modal
    model: str
    probes: Optional[List[str]] = None  # List of probe names (can be single-element list)
    temperature: float = 0.7
    max_tokens: int = 512
    system_prompt: str = ""
    can_see_probes: bool = False  # If True, this player can see probe scores in prompts
    omniscient_view: bool = False  # If True, this player can see all players' hands and full game state

    def __post_init__(self):
        """Validate probe-model compatibility."""
        if self.probes is None or len(self.probes) == 0:
            return  # No probes to validate

        # Extract model size from model string
        model_lower = self.model.lower()
        model_size = None

        # Check for common model sizes in the model string
        if '8b' in model_lower or '8-b' in model_lower:
            model_size = '8b'
        elif '70b' in model_lower or '70-b' in model_lower:
            model_size = '70b'
        elif '405b' in model_lower or '405-b' in model_lower:
            model_size = '405b'
        # Claude and other non-Llama models don't support probes
        elif 'claude' in model_lower or 'gpt' in model_lower or 'sonnet' in model_lower:
            raise ValueError(
                f"Probes are only supported for Llama models, not '{self.model}'. "
                f"Remove probes={self.probes} or use a Llama model."
            )

        if model_size is None:
            # Couldn't determine model size - warn but don't fail
            import warnings
            warnings.warn(
                f"Could not determine model size from '{self.model}' to validate probes {self.probes}. "
                f"Ensure probes match your model (e.g., deception_8b for 8B models, deception_70b for 70B models)."
            )
            return

        # Validate each probe matches the model size
        for probe in self.probes:
            probe_lower = probe.lower()

            # Extract size from probe name (e.g., "deception_8b" -> "8b")
            probe_size = None
            if '8b' in probe_lower or '8-b' in probe_lower:
                probe_size = '8b'
            elif '70b' in probe_lower or '70-b' in probe_lower:
                probe_size = '70b'
            elif '405b' in probe_lower or '405-b' in probe_lower:
                probe_size = '405b'

            if probe_size is None:
                import warnings
                warnings.warn(
                    f"Could not determine size from probe name '{probe}'. "
                    f"Expected format like 'deception_8b' or 'hallucination_70b'."
                )
                continue

            # Check for mismatch
            if probe_size != model_size:
                raise ValueError(
                    f"Probe-model mismatch for player '{self.name}': "
                    f"Probe '{probe}' ({probe_size}) does not match model '{self.model}' ({model_size}). "
                    f"Use {probe.replace(probe_size, model_size)} instead or change the model."
                )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "backend_type": self.backend_type,
            "model": self.model,
            "probes": self.probes,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
            "can_see_probes": self.can_see_probes,
            "omniscient_view": self.omniscient_view,
        }
