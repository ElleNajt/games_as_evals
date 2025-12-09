"""Training methods for activation probes.

All training methods are implemented in this single file.
Each method takes a dataset and config, and returns (probe_weights, metrics).
"""

import torch
import torch.nn as nn
import torch.optim as optim
from typing import Tuple, Dict, Any, List
from .dataset import Dataset, ContrastivePair
from .config import TrainingConfig


def train_linear_contrastive(
    dataset: Dataset,
    config: TrainingConfig,
    activations_fn=None  # Function to get activations for a text
) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """Train linear probe with contrastive loss.
    
    Minimizes distance between positive activations and a "truth direction",
    while maximizing distance for negative activations.
    
    Args:
        dataset: Dataset to train on
        config: Training configuration
        activations_fn: Function that takes text and returns activations tensor
        
    Returns:
        (probe_weights, metrics) where:
            - probe_weights: Trained linear probe weights
            - metrics: Training metrics (loss, accuracy, etc.)
    """
    # TODO: Implement linear contrastive training
    # This is a stub for now
    raise NotImplementedError("Linear contrastive training not yet implemented")


def train_massmean(
    dataset: Dataset,
    config: TrainingConfig,
    activations_fn=None
) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """Train mass-mean probe (difference of means).
    
    Simple method: probe = mean(positive_activations) - mean(negative_activations)
    No gradient descent required.
    
    Args:
        dataset: Dataset to train on
        config: Training configuration
        activations_fn: Function that takes text and returns activations tensor
        
    Returns:
        (probe_weights, metrics)
    """
    # TODO: Implement mass-mean training
    # This is a stub for now
    raise NotImplementedError("Mass-mean training not yet implemented")


def train_lda(
    dataset: Dataset,
    config: TrainingConfig,
    activations_fn=None
) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """Train LDA (Linear Discriminant Analysis) probe.
    
    Finds linear direction that maximizes separation between positive and negative
    activations using Fisher's Linear Discriminant.
    
    Args:
        dataset: Dataset to train on
        config: Training configuration
        activations_fn: Function that takes text and returns activations tensor
        
    Returns:
        (probe_weights, metrics)
    """
    # TODO: Implement LDA training
    # This is a stub for now
    raise NotImplementedError("LDA training not yet implemented")


def train_lat(
    dataset: Dataset,
    config: TrainingConfig,
    activations_fn=None
) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """Train LAT (Linear Artificial Tomography) probe.
    
    Advanced method from Apollo research.
    
    Args:
        dataset: Dataset to train on
        config: Training configuration
        activations_fn: Function that takes text and returns activations tensor
        
    Returns:
        (probe_weights, metrics)
    """
    # TODO: Implement LAT training
    # This is a stub for now
    raise NotImplementedError("LAT training not yet implemented")


# Registry of all available training methods
TRAINING_METHODS = {
    "linear-contrastive": train_linear_contrastive,
    "massmean": train_massmean,
    "lda": train_lda,
    "lat": train_lat,
}


def get_training_method(method_name: str):
    """Get training method function by name.
    
    Args:
        method_name: Name of training method
        
    Returns:
        Training function
        
    Raises:
        ValueError: If method not found
    """
    if method_name not in TRAINING_METHODS:
        available = ", ".join(TRAINING_METHODS.keys())
        raise ValueError(
            f"Unknown training method: {method_name}\n"
            f"Available methods: {available}"
        )
    return TRAINING_METHODS[method_name]
