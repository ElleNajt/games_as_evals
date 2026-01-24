"""Training methods for activation probes.

All training methods are implemented in this single file.
Each method takes activation data and config, and returns (probe_weights, metrics).
"""

import torch
import torch.nn as nn
import torch.optim as optim
import einops
from typing import Tuple, Dict, Any
from jaxtyping import Float
from torch import Tensor

from .activations import ActivationData
from .config import TrainingConfig


def train_linear_contrastive(
    activation_data: ActivationData,
    config: TrainingConfig
) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """Train linear probe with contrastive loss.

    Uses PyTorch optimization to find a direction that maximizes the dot product
    with positive examples and minimizes it with negative examples.

    Args:
        activation_data: Extracted activations for positive and negative examples
        config: Training configuration (use additional_params['l2_reg'] for L2 regularization strength)

    Returns:
        (probe_weights, metrics) where:
            - probe_weights: Trained linear probe weights [hidden_dim]
            - metrics: Training metrics (loss, accuracy, etc.) including normalization parameters
    """
    device = torch.device(config.device)
    pos_acts = activation_data.positive_acts.to(device).to(torch.float32)
    neg_acts = activation_data.negative_acts.to(device).to(torch.float32)

    # Get normalization setting (default True for Apollo compatibility)
    normalize = config.additional_params.get('normalize', True)

    # Normalize activations if requested
    if normalize:
        # Concatenate all training activations
        all_acts = torch.cat([pos_acts, neg_acts], dim=0)

        # Compute mean and std for normalization
        acts_mean = all_acts.mean(dim=0, keepdim=True)
        acts_std = all_acts.std(dim=0, keepdim=True)
        acts_std = torch.clamp(acts_std, min=1e-8)  # Prevent division by zero

        # Normalize activations
        pos_acts = (pos_acts - acts_mean) / acts_std
        neg_acts = (neg_acts - acts_mean) / acts_std
    else:
        acts_mean = None
        acts_std = None

    hidden_dim = pos_acts.shape[1]

    # Get L2 regularization strength from config (default to 0.0 if not specified)
    l2_reg = config.additional_params.get('l2_reg', 0.0)

    # Initialize probe direction
    direction = nn.Parameter(torch.randn(hidden_dim, device=device, dtype=torch.float32))
    optimizer = optim.Adam([direction], lr=config.learning_rate)

    best_loss = float('inf')
    best_direction = None

    for epoch in range(config.num_epochs):
        optimizer.zero_grad()

        # Normalize direction
        norm_direction = direction / (direction.norm() + 1e-8)

        # Compute scores
        pos_scores = pos_acts @ norm_direction  # [n_pos]
        neg_scores = neg_acts @ norm_direction  # [n_neg]

        # Contrastive loss: want positive scores high, negative scores low
        contrastive_loss = -pos_scores.mean() + neg_scores.mean()

        # Add L2 regularization penalty (on the unnormalized direction)
        l2_penalty = l2_reg * (direction.norm() ** 2)

        # Total loss
        loss = contrastive_loss + l2_penalty

        loss.backward()
        optimizer.step()

        if loss.item() < best_loss:
            best_loss = loss.item()
            best_direction = norm_direction.detach().clone()

    # Compute final metrics
    with torch.no_grad():
        final_direction = best_direction / (best_direction.norm() + 1e-8)
        pos_scores = pos_acts @ final_direction
        neg_scores = neg_acts @ final_direction

        # Classification accuracy (threshold at 0)
        correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
        total = len(pos_scores) + len(neg_scores)
        accuracy = (correct.float() / total).item()

    metrics = {
        "final_loss": best_loss,
        "accuracy": accuracy,
        "mean_pos_score": pos_scores.mean().item(),
        "mean_neg_score": neg_scores.mean().item(),
        "separation": (pos_scores.mean() - neg_scores.mean()).item(),
        "l2_reg": l2_reg,  # Include the L2 regularization strength used
        "normalize": normalize,
        "normalization_mean": acts_mean.cpu().squeeze() if acts_mean is not None else None,
        "normalization_std": acts_std.cpu().squeeze() if acts_std is not None else None,
    }

    return final_direction.cpu(), metrics


def train_massmean(
    activation_data: ActivationData,
    config: TrainingConfig
) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """Train mass-mean probe (difference of means).

    Simple method: probe = mean(positive_activations) - mean(negative_activations)
    No gradient descent required. This is also called Mean-Mean Subtraction (MMS).

    Args:
        activation_data: Extracted activations for positive and negative examples
        config: Training configuration

    Returns:
        (probe_weights, metrics)
    """
    pos_acts = activation_data.positive_acts.to(torch.float32)
    neg_acts = activation_data.negative_acts.to(torch.float32)

    # Get normalization setting (default True for Apollo compatibility)
    normalize = config.additional_params.get('normalize', True)

    # Normalize activations if requested
    if normalize:
        # Concatenate all training activations
        all_acts = torch.cat([pos_acts, neg_acts], dim=0)

        # Compute mean and std for normalization
        acts_mean = all_acts.mean(dim=0, keepdim=True)
        acts_std = all_acts.std(dim=0, keepdim=True)
        acts_std = torch.clamp(acts_std, min=1e-8)  # Prevent division by zero

        # Normalize activations
        pos_acts = (pos_acts - acts_mean) / acts_std
        neg_acts = (neg_acts - acts_mean) / acts_std
    else:
        acts_mean = None
        acts_std = None

    # Compute mean activations
    pos_mean = pos_acts.mean(dim=0)  # [hidden_dim]
    neg_mean = neg_acts.mean(dim=0)  # [hidden_dim]

    # Direction is difference of means
    direction = pos_mean - neg_mean  # [hidden_dim]

    # Normalize
    direction = direction / (direction.norm() + 1e-8)

    # Compute metrics
    with torch.no_grad():
        pos_scores = pos_acts @ direction
        neg_scores = neg_acts @ direction

        # Classification accuracy (threshold at 0)
        correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
        total = len(pos_scores) + len(neg_scores)
        accuracy = (correct.float() / total).item()

    metrics = {
        "accuracy": accuracy,
        "mean_pos_score": pos_scores.mean().item(),
        "mean_neg_score": neg_scores.mean().item(),
        "separation": (pos_scores.mean() - neg_scores.mean()).item(),
        "normalize": normalize,
        "normalization_mean": acts_mean.cpu().squeeze() if acts_mean is not None else None,
        "normalization_std": acts_std.cpu().squeeze() if acts_std is not None else None,
    }

    return direction, metrics


def train_lda(
    activation_data: ActivationData,
    config: TrainingConfig
) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """Train LDA (Linear Discriminant Analysis) probe.

    Finds linear direction that maximizes separation between positive and negative
    activations using Fisher's Linear Discriminant (covariance-adjusted MMS).

    Args:
        activation_data: Extracted activations for positive and negative examples
        config: Training configuration

    Returns:
        (probe_weights, metrics)
    """
    device = torch.device(config.device)
    dtype = torch.float32

    pos_acts = activation_data.positive_acts.to(device).to(dtype)
    neg_acts = activation_data.negative_acts.to(device).to(dtype)

    # Get normalization setting (default True for Apollo compatibility)
    normalize = config.additional_params.get('normalize', True)

    # Normalize activations if requested
    if normalize:
        # Concatenate all training activations
        all_acts = torch.cat([pos_acts, neg_acts], dim=0)

        # Compute mean and std for normalization
        acts_mean = all_acts.mean(dim=0, keepdim=True)
        acts_std = all_acts.std(dim=0, keepdim=True)
        acts_std = torch.clamp(acts_std, min=1e-8)  # Prevent division by zero

        # Normalize activations
        pos_acts = (pos_acts - acts_mean) / acts_std
        neg_acts = (neg_acts - acts_mean) / acts_std
    else:
        acts_mean = None
        acts_std = None

    # Compute mean difference
    pos_mean = pos_acts.mean(dim=0)
    neg_mean = neg_acts.mean(dim=0)
    mean_diff = pos_mean - neg_mean

    # Compute covariance matrices
    pos_cov = torch.cov(pos_acts.T, correction=0)  # [hidden_dim, hidden_dim]
    neg_cov = torch.cov(neg_acts.T, correction=0)  # [hidden_dim, hidden_dim]

    # Average covariance (pooled covariance)
    cov_matrix = (pos_cov + neg_cov) / 2  # [hidden_dim, hidden_dim]

    # Fisher's Linear Discriminant: Σ^{-1} * (μ_pos - μ_neg)
    cov_inv = torch.linalg.pinv(cov_matrix)
    direction = cov_inv @ mean_diff

    # Normalize
    direction = direction / (direction.norm() + 1e-8)

    # Compute metrics
    with torch.no_grad():
        pos_scores = pos_acts @ direction
        neg_scores = neg_acts @ direction

        # Classification accuracy (threshold at 0)
        correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
        total = len(pos_scores) + len(neg_scores)
        accuracy = (correct.float() / total).item()

    metrics = {
        "accuracy": accuracy,
        "mean_pos_score": pos_scores.mean().item(),
        "mean_neg_score": neg_scores.mean().item(),
        "separation": (pos_scores.mean() - neg_scores.mean()).item(),
        "normalize": normalize,
        "normalization_mean": acts_mean.cpu().squeeze() if acts_mean is not None else None,
        "normalization_std": acts_std.cpu().squeeze() if acts_std is not None else None,
    }

    return direction.cpu(), metrics


def train_lat(
    activation_data: ActivationData,
    config: TrainingConfig
) -> Tuple[torch.Tensor, Dict[str, Any]]:
    """Train LAT (Linear Artificial Tomography) probe.

    Method from the Representation Engineering paper (Apollo research).
    Computes PCA on randomly flipped difference vectors.

    Args:
        activation_data: Extracted activations for positive and negative examples
        config: Training configuration

    Returns:
        (probe_weights, metrics)
    """
    device = torch.device(config.device)
    dtype = torch.float32

    pos_acts = activation_data.positive_acts.to(device).to(dtype)
    neg_acts = activation_data.negative_acts.to(device).to(dtype)

    # Get normalization setting (default True for Apollo compatibility)
    normalize = config.additional_params.get('normalize', True)

    # Normalize activations if requested
    if normalize:
        # Concatenate all training activations
        all_acts = torch.cat([pos_acts, neg_acts], dim=0)

        # Compute mean and std for normalization
        acts_mean = all_acts.mean(dim=0, keepdim=True)
        acts_std = all_acts.std(dim=0, keepdim=True)
        acts_std = torch.clamp(acts_std, min=1e-8)  # Prevent division by zero

        # Normalize activations
        pos_acts = (pos_acts - acts_mean) / acts_std
        neg_acts = (neg_acts - acts_mean) / acts_std
    else:
        acts_mean = None
        acts_std = None

    # Compute difference vectors
    diffs = pos_acts - neg_acts  # [n_examples, hidden_dim]

    # Randomly flip signs of half the differences
    torch.manual_seed(config.seed)
    signs = torch.where(torch.randn(len(diffs), device=device) > 0, 1, -1)
    diffs *= signs[:, None]

    # Find first PCA component (mean-centered)
    _, _, V = torch.pca_lowrank(diffs, q=1, center=True)
    direction = V[:, 0]  # [hidden_dim]

    # Ensure direction points in positive direction
    # (positive examples should have higher scores than negative)
    pos_scores = pos_acts @ direction
    neg_scores = neg_acts @ direction

    if pos_scores.mean() < neg_scores.mean():
        direction = -direction

    # Compute final metrics
    with torch.no_grad():
        pos_scores = pos_acts @ direction
        neg_scores = neg_acts @ direction

        # Classification accuracy (threshold at 0)
        correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
        total = len(pos_scores) + len(neg_scores)
        accuracy = (correct.float() / total).item()

    metrics = {
        "accuracy": accuracy,
        "mean_pos_score": pos_scores.mean().item(),
        "mean_neg_score": neg_scores.mean().item(),
        "separation": (pos_scores.mean() - neg_scores.mean()).item(),
        "normalize": normalize,
        "normalization_mean": acts_mean.cpu().squeeze() if acts_mean is not None else None,
        "normalization_std": acts_std.cpu().squeeze() if acts_std is not None else None,
    }

    return direction.cpu(), metrics


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
