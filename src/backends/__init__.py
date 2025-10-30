"""Backend implementations for different LLM providers."""

from .base import LLMBackend, GenerationResult, ProbeScores
from .claude_backend import ClaudeBackend
from .openrouter_backend import OpenRouterBackend
from .modal_backend import ModalBackend


def create_backend(
    backend_type: str,
    probe: str = None,
    **kwargs
) -> LLMBackend:
    """
    Factory function to create LLM backends.
    
    Args:
        backend_type: One of ["claude", "openrouter", "modal"]
        probe: Probe name from registry (e.g., "deception_8b", "hallucination_8b")
               Only used for Modal backend.
        **kwargs: Backend-specific configuration
        
    Returns:
        LLMBackend instance
        
    Examples:
        >>> backend = create_backend("claude")
        >>> backend = create_backend("openrouter", model="meta-llama/llama-3.1-70b-instruct")
        >>> backend = create_backend("modal", probe="deception_8b")
    """
    if backend_type == "claude":
        return ClaudeBackend()
    
    elif backend_type == "openrouter":
        return OpenRouterBackend(
            model=kwargs.get("model", "anthropic/claude-3.5-sonnet"),
            api_key=kwargs.get("api_key")
        )
    
    elif backend_type == "modal":
        return ModalBackend(
            probe=probe,
            modal_app_name=kwargs.get("modal_app_name"),
            **kwargs
        )
    
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


__all__ = [
    "LLMBackend",
    "GenerationResult",
    "ProbeScores",
    "create_backend",
    "ClaudeBackend",
    "OpenRouterBackend", 
    "ModalBackend",
]
