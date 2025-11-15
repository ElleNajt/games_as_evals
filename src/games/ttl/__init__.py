"""Two Truths and a Lie Deception Game - Unified Backend Version"""

# Only export config for now - modules can be imported directly if needed
from .config import TTLConfig, TTLPlayerConfig

__all__ = [
    "TTLConfig",
    "TTLPlayerConfig",
]
