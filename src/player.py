"""Unified player abstraction for all games."""

from typing import Optional
from .backends.base import LLMBackend, GenerationResult


class GamePlayer:
    """
    Unified player abstraction that wraps any LLM backend.
    
    This is the single interface that all games should use.
    Games handle their own prompt formatting and response parsing.
    """
    
    def __init__(
        self,
        name: str,
        backend: LLMBackend,
        system_prompt: str = ""
    ):
        """
        Create a game player.
        
        Args:
            name: Player name (e.g., "Alice", "Bob")
            backend: LLM backend instance
            system_prompt: System prompt describing the player's role
        """
        self.name = name
        self.backend = backend
        self.system_prompt = system_prompt
    
    def query(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> GenerationResult:
        """
        Query the player with a prompt.
        
        Args:
            prompt: User prompt to send to the LLM
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = random)
            
        Returns:
            GenerationResult with:
                - text: Generated response (always present)
                - tokens: Token list (Modal only, else None)
                - top_k_logits: Top-k logits per token (Modal only, else None)
                - probe_scores: Probe scores (Modal with probe only, else None)
                
        Example:
            >>> backend = create_backend("modal", probe="deception_8b")
            >>> alice = GamePlayer("Alice", backend, "You are a strategic player...")
            >>> result = alice.query("What's your move?")
            >>> print(result.text)
            >>> if result.probe_scores:
            ...     print(f"Deception score: {result.probe_scores.aggregate_score}")
        """
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        return self.backend.generate(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
