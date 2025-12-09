"""Probe training infrastructure for deception and hallucination detection.

This module provides tools for:
- Training activation probes on contrastive datasets
- Managing probe versioning and storage
- Downloading and caching probes from HuggingFace
- Verifying dataset and probe integrity via checksums
"""

# Import lightweight components by default
from .config import TrainingConfig
from .dataset import Dataset
from .registry import ProbeRegistry, ProbeMetadata

# Heavy dependencies (torch, transformers, etc.) are imported lazily
# Import them directly from submodules when needed:
#   from probe_training.methods import TRAINING_METHODS, get_training_method
#   from probe_training.activations import extract_contrastive_activations, load_model_and_tokenizer

__all__ = [
    "TrainingConfig",
    "Dataset",
    "ProbeRegistry",
    "ProbeMetadata",
]
