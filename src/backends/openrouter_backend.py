"""OpenRouter API backend implementation."""

import os
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv
from .base import LLMBackend, GenerationResult

load_dotenv()


class OpenRouterBackend(LLMBackend):
    """
    Backend using OpenRouter API.
    
    Does NOT support probes or logits - only returns text.
    Supports various models via OpenRouter.
    """
    
    def __init__(
        self,
        model: str = "anthropic/claude-3.5-sonnet",
        api_key: Optional[str] = None
    ):
        """
        Initialize OpenRouter backend.
        
        Args:
            model: Model identifier (e.g., "meta-llama/llama-3.1-70b-instruct")
            api_key: OpenRouter API key (or set OPENROUTER_API_KEY env var)
        """
        self.model = model
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key not found. "
                "Set OPENROUTER_API_KEY env var or pass api_key."
            )
        
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """
        Generate using OpenRouter API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            GenerationResult with only text populated
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        response = requests.post(self.base_url, headers=headers, json=data, timeout=120)
        
        if response.status_code != 200:
            raise RuntimeError(
                f"OpenRouter API error (status {response.status_code}): {response.text}"
            )
        
        result = response.json()
        
        if "error" in result:
            raise RuntimeError(f"OpenRouter API error: {result['error']}")
        
        text = result["choices"][0]["message"]["content"]
        
        return GenerationResult(
            text=text,
            tokens=None,
            top_k_logits=None,
            probe_scores=None
        )
    
    @property
    def supports_probes(self) -> bool:
        return False
    
    @property
    def supports_logits(self) -> bool:
        return False
