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
