"""Backend implementations for different LLM providers."""

from .base import LLMBackend, GenerationResult, ProbeScores, ProbeScoreData
from .claude_backend import ClaudeBackend
from .openrouter_backend import OpenRouterBackend
from .modal_backend import ModalBackend


# Default probe sets for each model size
# By default, run both deception and hallucination probes to save money
DEFAULT_PROBES_BY_MODEL = {
    "meta-llama/Meta-Llama-3.1-8B-Instruct": ["deception_8b", "hallucination_8b"],
    "meta-llama/Llama-3.3-70B-Instruct": ["deception_70b"],  # Only deception for 70B for now
}


def create_backend(
    backend_type: str,
    model: str = None,
    probe: str = None,
    probes: list = None,
    **kwargs
) -> LLMBackend:
    """
    Factory function to create LLM backends.
    
    Args:
        backend_type: One of ["claude", "openrouter", "modal"]
        model: Model name (required for modal to determine default probes)
        probe: Single probe name (backward compat) - converted to list internally
        probes: List of probe names (overrides defaults)
               Only used for Modal backend.
        **kwargs: Backend-specific configuration
        
    Returns:
        LLMBackend instance
        
    Examples:
        >>> # Claude backend
        >>> backend = create_backend("claude")
        
        >>> # Modal with default probes (both deception + hallucination for 8B)
        >>> backend = create_backend("modal", model="meta-llama/Meta-Llama-3.1-8B-Instruct")
        
        >>> # Modal with specific single probe (backward compat)
        >>> backend = create_backend("modal", model="...", probe="deception_8b")
        
        >>> # Modal with specific probe list
        >>> backend = create_backend("modal", model="...", probes=["hallucination_8b"])
    """
    if backend_type == "claude":
        return ClaudeBackend()
    
    elif backend_type == "openrouter":
        return OpenRouterBackend(
            model=model or kwargs.get("model", "anthropic/claude-3.5-sonnet"),
            api_key=kwargs.get("api_key")
        )
    
    elif backend_type == "modal":
        # Handle probe defaults for Modal
        # Priority: probes list > single probe > model defaults
        if probe and not probes:
            # Backward compat: single probe
            probes = [probe]
        elif not probes and model and model in DEFAULT_PROBES_BY_MODEL:
            # Use defaults for this model
            probes = DEFAULT_PROBES_BY_MODEL[model]
            print(f"Using default probes for {model}: {probes}")
        
        return ModalBackend(
            probes=probes,
            modal_app_name=kwargs.get("modal_app_name"),
            **kwargs
        )
    
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


__all__ = [
    "LLMBackend",
    "GenerationResult",
    "ProbeScores",
    "ProbeScoreData",
    "create_backend",
    "ClaudeBackend",
    "OpenRouterBackend", 
    "ModalBackend",
]
