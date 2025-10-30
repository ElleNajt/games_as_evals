"""
Unified backend system for LLM-based games.

This package provides a common interface for different LLM backends
(Modal, OpenRouter, Claude) with optional probe integration.
"""

from .backends.base import LLMBackend, GenerationResult, ProbeScores
from .backends import create_backend
from .player import GamePlayer

__all__ = [
    "LLMBackend",
    "GenerationResult", 
    "ProbeScores",
    "create_backend",
    "GamePlayer",
]
