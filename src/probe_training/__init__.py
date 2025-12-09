"""Probe training infrastructure for deception and hallucination detection.

This module provides tools for:
- Training activation probes on contrastive datasets
- Managing probe versioning and storage
- Downloading and caching probes from HuggingFace
- Verifying dataset and probe integrity via checksums
"""

from .config import TrainingConfig
from .dataset import Dataset
from .registry import ProbeRegistry, ProbeMetadata
from .methods import TRAINING_METHODS, get_training_method
from .activations import (
    ActivationData,
    extract_contrastive_activations,
    load_model_and_tokenizer
)

__all__ = [
    "TrainingConfig",
    "Dataset",
    "ProbeRegistry",
    "ProbeMetadata",
    "TRAINING_METHODS",
    "get_training_method",
    "ActivationData",
    "extract_contrastive_activations",
    "load_model_and_tokenizer",
]
