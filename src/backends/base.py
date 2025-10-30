"""Base classes and data structures for LLM backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ProbeScores:
    """
    Probe scoring information from activation probes.
    
    Only populated by Modal backend. Other backends return None.
    """
    aggregate_score: float
    """Mean/summary score across all tokens"""
    
    token_scores: List[float]
    """Per-token probe scores"""
    
    phase_scores: Optional[Dict[str, float]] = None
    """Phase-based scores (e.g., prompt/CoT/action for Werewolf)"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Game-specific metadata (num_tokens, etc.)"""


@dataclass
class GenerationResult:
    """
    Unified response format from any LLM backend.
    
    All backends return text.
    Only Modal backend populates tokens, top_k_logits, and probe_scores.
    Other backends return None for these fields.
    """
    text: str
    """Generated text response"""
    
    tokens: Optional[List[str]] = None
    """Token list (Modal only)"""
    
    top_k_logits: Optional[List[Dict[str, float]]] = None
    """Top-k logits per token (Modal only, if requested)"""
    
    probe_scores: Optional[ProbeScores] = None
    """Probe activation scores (Modal only, if probe enabled)"""


class LLMBackend(ABC):
    """Abstract base class for LLM backends."""
    
    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """
        Generate text from messages.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     Example: [{"role": "system", "content": "..."}, 
                               {"role": "user", "content": "..."}]
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = random)
            
        Returns:
            GenerationResult with text and optional probe data
        """
        pass
    
    @property
    @abstractmethod
    def supports_probes(self) -> bool:
        """Does this backend support probe scoring?"""
        pass
    
    @property
    @abstractmethod
    def supports_logits(self) -> bool:
        """Does this backend return top-k logits?"""
        pass
