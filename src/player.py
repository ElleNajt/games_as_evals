"""Unified player abstraction for all games."""

from typing import Optional, TYPE_CHECKING
from .backends.base import LLMBackend, GenerationResult

if TYPE_CHECKING:
    from .logging.results_logger import ResultsLogger


class GamePlayer:
    """
    Unified player abstraction that wraps any LLM backend.
    
    This is the single interface that all games should use.
    Games handle their own prompt formatting and response parsing.
    
    Optionally logs all interactions to a ResultsLogger.
    """
    
    def __init__(
        self,
        name: str,
        backend: LLMBackend,
        system_prompt: str = "",
        logger: Optional["ResultsLogger"] = None
    ):
        """
        Create a game player.
        
        Args:
            name: Player name (e.g., "Alice", "Bob")
            backend: LLM backend instance
            system_prompt: System prompt describing the player's role
            logger: Optional ResultsLogger for automatic message logging
        """
        self.name = name
        self.backend = backend
        self.system_prompt = system_prompt
        self.logger = logger
    
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
        
        result = self.backend.generate(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # Log interaction if logger is configured
        if self.logger:
            self.logger.log_message(
                player_name=self.name,
                role="assistant",
                prompt=prompt,
                response=result.text,
                tokens=result.tokens,
                top_k_logits=result.top_k_logits,
                probe_scores=result.probe_scores,
                metadata={
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "system_prompt": self.system_prompt,
                }
            )
        
        return result
