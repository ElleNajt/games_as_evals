"""Probe training infrastructure for deception and hallucination detection.

This module provides tools for:
- Training activation probes on contrastive datasets
- Managing probe versioning and storage
- Downloading and caching probes from HuggingFace
- Verifying dataset and probe integrity via checksums
"""

from .config import TrainingConfig
from .dataset import Dataset
from .registry import ProbeRegistry
from .methods import TRAINING_METHODS

__all__ = [
    "TrainingConfig",
    "Dataset",
    "ProbeRegistry",
    "TRAINING_METHODS",
]
