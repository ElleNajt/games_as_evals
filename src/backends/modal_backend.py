"""Modal backend implementation with probe support."""

import modal
from typing import List, Dict, Optional, Any
from .base import LLMBackend, GenerationResult, ProbeScores
from ..probes.registry import get_probe_config


class ModalBackend(LLMBackend):
    """
    Backend using Modal for generation with optional probe scoring.
    
    Supports probes, tokens, and optionally logits.
    Connects to existing Modal deployments (werewolf-apollo-probe, etc.)
    """
    
    def __init__(
        self,
        probe: Optional[str] = None,
        modal_app_name: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Modal backend.
        
        Args:
            probe: Probe name from registry (e.g., "deception_8b", "hallucination_8b")
                  If None, no probe scoring is performed.
            modal_app_name: Override Modal app name (defaults to probe config)
            **kwargs: Additional config (unused for now)
        """
        self.probe_name = probe
        self.probe_config = get_probe_config(probe) if probe else None
        self.modal_app_name = modal_app_name or (
            self.probe_config.modal_app_name if self.probe_config else None
        )
        self.service = None
        
        if not self.modal_app_name:
            raise ValueError(
                "modal_app_name must be provided if probe is None. "
                "Either specify probe (e.g., 'deception_8b') or modal_app_name."
            )
        
        print(f"ModalBackend initialized (app={self.modal_app_name}, probe={probe})")
    
    def _ensure_connected(self):
        """Lazy connect to Modal service."""
        if self.service is None:
            print(f"Connecting to Modal app '{self.modal_app_name}'...")
            
            # Determine service class name based on app
            if "werewolf" in self.modal_app_name or "apollo" in self.modal_app_name:
                service_class_name = "ApolloProbeService"
            elif "hallucination" in self.modal_app_name:
                service_class_name = "ProbeInferenceService"
            else:
                # Default assumption
                service_class_name = "ApolloProbeService"
            
            cls = modal.Cls.from_name(self.modal_app_name, service_class_name)
            self.service = cls()
            
            print(f"Connected to Modal service {service_class_name}!")
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """
        Generate using Modal with optional probe scoring.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            GenerationResult with text, tokens, and probe_scores (if probe enabled)
        """
        self._ensure_connected()
        
        # Choose generation method based on whether probe is enabled
        if self.probe_config:
            # Generate with probe scoring
            result = self._generate_with_probe(messages, max_tokens, temperature)
        else:
            # Standard generation without probe
            result = self._generate_without_probe(messages, max_tokens, temperature)
        
        return result
    
    def _generate_with_probe(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float
    ) -> GenerationResult:
        """Generate with probe scoring enabled."""
        # Use generate_with_probe method
        try:
            result = self.service.generate_with_probe.remote(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
        except AttributeError:
            # Try alternative method name for hallucination probes
            result = self.service.predict_conversation.remote(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
        
        if "error" in result:
            raise RuntimeError(f"Modal generation failed: {result['error']}")
        
        # Extract text
        text = result.get("generated_text") or result.get("text", "")
        
        # Extract probe scores
        probe_scores = None
        if "aggregate_score" in result or "token_scores" in result:
            aggregate = result.get("aggregate_score") or result.get("mean_score", 0.0)
            token_scores = result.get("token_scores", [])
            
            # Handle different probe result formats
            phase_scores = None
            if "prompt_score" in result:  # Werewolf 3-phase format
                phase_scores = {
                    "prompt": result.get("prompt_score"),
                    "cot": result.get("cot_score"),
                    "action": result.get("action_score"),
                    "generation": result.get("generation_score"),
                }
            
            metadata = {
                "num_tokens": result.get("num_tokens") or len(token_scores),
                "probe_type": self.probe_config.probe_type if self.probe_config else "unknown",
            }
            
            probe_scores = ProbeScores(
                aggregate_score=aggregate,
                token_scores=token_scores,
                phase_scores=phase_scores,
                metadata=metadata
            )
        
        # Extract tokens
        tokens = result.get("tokens")
        
        return GenerationResult(
            text=text,
            tokens=tokens,
            top_k_logits=None,  # Not currently extracted
            probe_scores=probe_scores
        )
    
    def _generate_without_probe(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float
    ) -> GenerationResult:
        """Generate without probe scoring."""
        result = self.service.generate.remote(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        if "error" in result:
            raise RuntimeError(f"Modal generation failed: {result['error']}")
        
        text = result.get("generated_text") or result.get("text", "")
        tokens = result.get("tokens")
        
        return GenerationResult(
            text=text,
            tokens=tokens,
            top_k_logits=None,
            probe_scores=None
        )
    
    @property
    def supports_probes(self) -> bool:
        return self.probe_config is not None
    
    @property
    def supports_logits(self) -> bool:
        return False  # Not currently implemented
