"""Base classes and data structures for LLM backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ProbeScoreData:
    """
    Scoring information from a single activation probe.
    """
    aggregate_score: float
    """Mean/summary score across all tokens"""
    
    token_scores: List[float]
    """Per-token probe scores (generation tokens only)"""
    
    prompt_token_scores: Optional[List[float]] = None
    """Per-token probe scores for prompt tokens"""
    
    phase_scores: Optional[Dict[str, float]] = None
    """Phase-based scores (e.g., prompt/CoT/action for Werewolf)"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Probe-specific metadata"""


@dataclass
class ProbeScores:
    """
    Probe scoring information from activation probes.
    
    Supports multiple probes running simultaneously.
    Only populated by Modal backend. Other backends return None.
    """
    scores: Dict[str, ProbeScoreData]
    """Probe scores keyed by probe name (e.g., {"deception_8b": ..., "hallucination_8b": ...})"""
    
    def __getitem__(self, probe_name: str) -> ProbeScoreData:
        """Allow dict-like access: probe_scores["deception_8b"]"""
        return self.scores[probe_name]
    
    def __contains__(self, probe_name: str) -> bool:
        """Allow 'in' checks: if "deception_8b" in probe_scores"""
        return probe_name in self.scores
    
    def keys(self):
        """Return probe names"""
        return self.scores.keys()
    
    # Backward compatibility: access first probe's scores directly
    @property
    def aggregate_score(self) -> float:
        """Backward compat: return aggregate score from first probe"""
        if not self.scores:
            raise ValueError("No probe scores available")
        return list(self.scores.values())[0].aggregate_score
    
    @property
    def token_scores(self) -> List[float]:
        """Backward compat: return token scores from first probe"""
        if not self.scores:
            raise ValueError("No probe scores available")
        return list(self.scores.values())[0].token_scores
    
    @property
    def phase_scores(self) -> Optional[Dict[str, float]]:
        """Backward compat: return phase scores from first probe"""
        if not self.scores:
            raise ValueError("No probe scores available")
        return list(self.scores.values())[0].phase_scores
    
    @property
    def metadata(self) -> Dict[str, Any]:
        """Backward compat: return metadata from first probe"""
        if not self.scores:
            raise ValueError("No probe scores available")
        return list(self.scores.values())[0].metadata


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
    """Token list for generation (Modal only)"""
    
    prompt_tokens: Optional[List[str]] = None
    """Token list for prompt (Modal only)"""
    
    top_k_logits: Optional[List[Dict[str, float]]] = None
    """Top-k logits per token (Modal only, if requested)"""
    
    probe_scores: Optional[ProbeScores] = None
    """Probe activation scores (Modal only, if probes enabled)"""


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
