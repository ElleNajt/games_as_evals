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
    probe: Optional[str] = None
    probes: Optional[List[str]] = None
    temperature: float = 0.7
    max_tokens: int = 512
    system_prompt: str = ""
    
    def __post_init__(self):
        """Normalize probe/probes parameters for consistent handling."""
        # If both are specified, raise an error
        if self.probe is not None and self.probes is not None:
            raise ValueError("Cannot specify both 'probe' and 'probes' parameters")
        
        # If probe is specified, convert to probes list for internal consistency
        # Keep probe field for backward compatibility but use probes internally
        if self.probe is not None and self.probes is None:
            self.probes = [self.probe]
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "backend_type": self.backend_type,
            "model": self.model,
            "probe": self.probe,
            "probes": self.probes,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
        }
