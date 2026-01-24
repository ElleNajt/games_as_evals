"""Inference utilities for applying trained probes with normalization."""

import torch
from pathlib import Path
from typing import Optional, Union, Dict, Any
from jaxtyping import Float
from torch import Tensor


class ProbeInference:
    """Class for applying trained probes to new activations.

    Handles normalization using saved parameters from training.
    """

    def __init__(self, probe_path: Union[str, Path]):
        """Load a trained probe from file.

        Args:
            probe_path: Path to saved probe.pt file
        """
        self.probe_path = Path(probe_path)

        # Load probe data
        probe_data = torch.load(self.probe_path, map_location='cpu')

        # Handle both old format (just weights) and new format (dict with normalization)
        if isinstance(probe_data, dict):
            self.weights = probe_data['weights']
            self.normalize = probe_data.get('normalize', False)
            self.norm_mean = probe_data.get('normalization_mean')
            self.norm_std = probe_data.get('normalization_std')
        else:
            # Old format: just the weight tensor
            self.weights = probe_data
            self.normalize = False
            self.norm_mean = None
            self.norm_std = None

    def apply(
        self,
        activations: Float[Tensor, "batch hidden_dim"],
        return_logits: bool = False
    ) -> Float[Tensor, "batch"]:
        """Apply probe to activations.

        Args:
            activations: Activations to score [batch, hidden_dim]
            return_logits: If False, returns sigmoid(scores). If True, returns raw scores.

        Returns:
            Probe scores for each example
        """
        # Ensure correct dtype
        activations = activations.to(torch.float32)
        weights = self.weights.to(torch.float32)

        # Apply normalization if needed
        if self.normalize and self.norm_mean is not None and self.norm_std is not None:
            norm_mean = self.norm_mean.to(torch.float32)
            norm_std = self.norm_std.to(torch.float32)

            # Normalize activations using training statistics
            activations = (activations - norm_mean) / norm_std

        # Compute scores
        scores = activations @ weights  # [batch]

        if return_logits:
            return scores
        else:
            return torch.sigmoid(scores)

    def apply_to_sequence(
        self,
        activations: Float[Tensor, "batch seq_len hidden_dim"],
        attention_mask: Optional[Float[Tensor, "batch seq_len"]] = None,
        aggregation: str = "mean",
        return_logits: bool = False
    ) -> Float[Tensor, "batch"]:
        """Apply probe to a sequence of activations.

        Args:
            activations: Sequence activations [batch, seq_len, hidden_dim]
            attention_mask: Mask for valid tokens [batch, seq_len]
            aggregation: How to aggregate scores ("mean", "max", "last")
            return_logits: If False, returns sigmoid(scores). If True, returns raw scores.

        Returns:
            Aggregated probe scores for each sequence
        """
        batch_size, seq_len, hidden_dim = activations.shape

        # Reshape to apply probe
        flat_acts = activations.reshape(-1, hidden_dim)  # [batch * seq_len, hidden_dim]
        flat_scores = self.apply(flat_acts, return_logits=True)  # [batch * seq_len]
        scores = flat_scores.reshape(batch_size, seq_len)  # [batch, seq_len]

        # Apply attention mask if provided
        if attention_mask is not None:
            # Set scores for padded positions to very negative value
            scores = scores.masked_fill(~attention_mask.bool(), -1e9)

        # Aggregate scores
        if aggregation == "mean":
            if attention_mask is not None:
                # Weighted mean considering only valid tokens
                valid_scores = scores * attention_mask
                agg_scores = valid_scores.sum(dim=1) / attention_mask.sum(dim=1)
            else:
                agg_scores = scores.mean(dim=1)
        elif aggregation == "max":
            agg_scores = scores.max(dim=1).values
        elif aggregation == "last":
            if attention_mask is not None:
                # Get last valid token position
                last_pos = attention_mask.sum(dim=1) - 1
                agg_scores = scores[torch.arange(batch_size), last_pos]
            else:
                agg_scores = scores[:, -1]
        else:
            raise ValueError(f"Unknown aggregation method: {aggregation}")

        if return_logits:
            return agg_scores
        else:
            return torch.sigmoid(agg_scores)


def load_and_apply_probe(
    probe_path: Union[str, Path],
    activations: Float[Tensor, "... hidden_dim"],
    **kwargs
) -> Float[Tensor, "..."]:
    """Convenience function to load and apply a probe.

    Args:
        probe_path: Path to saved probe
        activations: Activations to score
        **kwargs: Additional arguments for ProbeInference.apply()

    Returns:
        Probe scores
    """
    probe = ProbeInference(probe_path)

    # Handle both single examples and sequences
    if activations.ndim == 2:
        return probe.apply(activations, **kwargs)
    elif activations.ndim == 3:
        return probe.apply_to_sequence(activations, **kwargs)
    else:
        raise ValueError(f"Expected 2D or 3D activations, got shape {activations.shape}")


# Example usage
if __name__ == "__main__":
    # Load a trained probe
    probe = ProbeInference("probes/deception_8b_layer12/probe.pt")

    # Apply to single activation
    activation = torch.randn(1, 4096)  # [batch=1, hidden_dim=4096]
    score = probe.apply(activation)
    print(f"Deception score: {score.item():.4f}")

    # Apply to sequence
    sequence = torch.randn(2, 100, 4096)  # [batch=2, seq_len=100, hidden_dim=4096]
    attention_mask = torch.ones(2, 100)
    scores = probe.apply_to_sequence(sequence, attention_mask, aggregation="mean")
    print(f"Deception scores: {scores}")