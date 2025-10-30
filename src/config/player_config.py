"""Player configuration for games."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PlayerConfig:
    """Configuration for a single player.
    
    Each player can have different backend, model, and probe settings.
    
    Attributes:
        name: Player name/identifier
        backend_type: Backend to use (claude, openrouter, modal)
        model: Model identifier (e.g., claude-3-5-sonnet-20241022, gpt-4, llama-3.1-8b)
        probe: Optional probe to use (deception_8b, deception_70b, hallucination_8b)
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        system_prompt: System prompt for the player
    """
    
    name: str
    backend_type: str  # claude, openrouter, modal
    model: str
    probe: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 512
    system_prompt: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "backend_type": self.backend_type,
            "model": self.model,
            "probe": self.probe,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
        }
