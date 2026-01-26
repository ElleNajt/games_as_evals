"""Probe registry for deception and hallucination probes."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProbeConfig:
    """Configuration for an activation probe."""

    probe_name: str
    """Short probe name (e.g., 'deception_8b', 'hallucination_8b')"""

    volume_path: str
    """Path to probe on Modal volume (relative to /models/probes/ or absolute)"""

    probe_type: str
    """Type of probe: 'deception' or 'hallucination'"""

    model_name: str
    """Compatible model (e.g., 'meta-llama/Meta-Llama-3.1-8B-Instruct')"""

    layer: int
    """Which model layer to probe (e.g., 12 for deception, 30 for hallucination)"""

    description: str = ""
    """Human-readable description"""

    # Modal service (now unified)
    modal_app_name: str = "unified-probe-service"
    """Modal deployment name (default: unified-probe-service)"""

    # GPU requirements (informational)
    gpu_type: str = "A10G"
    """GPU type required (e.g., 'A10G', 'H100')"""

    gpu_count: int = 1
    """Number of GPUs required"""

    estimated_memory_gb: int = 24
    """Estimated GPU memory usage in GB"""

    bias: float = 0.0
    """Bias term for sigmoid transformation (shifts decision boundary)"""


# Registry of available probes
PROBE_REGISTRY = {
    "deception_8b": ProbeConfig(
        probe_name="deception_8b",
        volume_path="deception_8b_layer12",  # Path on Modal volume
        probe_type="deception",
        model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
        layer=12,  # Apollo deception probe uses layer 12
        description="8B deception probe (Apollo social deception scenarios) for games like Werewolf/3-SAT",
        modal_app_name="unified-probe-service",
        gpu_type="A10G",
        gpu_count=1,
        estimated_memory_gb=20,
    ),
    "deception_8b_massmean": ProbeConfig(
        probe_name="deception_8b_massmean",
        volume_path="roleplaying_Meta-Llama-3.1-8B-Instruct_massmean_layer12",
        probe_type="deception",
        model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
        layer=12,
        description="8B deception probe (massmean method, 76.7% accuracy, 0.83 separation)",
        modal_app_name="unified-probe-service",
        gpu_type="A10G",
        gpu_count=1,
        estimated_memory_gb=20,
    ),
    "deception_70b": ProbeConfig(
        probe_name="deception_70b",
        volume_path="deception_70b_layer22",  # Path on Modal volume
        probe_type="deception",
        model_name="meta-llama/Llama-3.3-70B-Instruct",
        layer=22,
        description="70B deception probe (Apollo social deception scenarios) for games like Werewolf",
        modal_app_name="unified-probe-service-70b",
        gpu_type="H100",
        gpu_count=4,
        estimated_memory_gb=320,  # 4x 80GB H100s
    ),
    "hallucination_8b": ProbeConfig(
        probe_name="hallucination_8b",
        volume_path="hallucination_8b_layer30",  # Path on Modal volume
        probe_type="hallucination",
        model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
        layer=30,  # Layer 30 from TTLGame probe config
        description="8B hallucination probe for Two Truths and a Lie",
        modal_app_name="unified-probe-service",
        gpu_type="A10G",
        gpu_count=1,
        estimated_memory_gb=20,
    ),
    "hallucination_70b": ProbeConfig(
        probe_name="hallucination_70b",
        volume_path="hallucination_70b_layer30",  # Path on Modal volume
        probe_type="hallucination",
        model_name="meta-llama/Llama-3.3-70B-Instruct",
        layer=76,
        description="70B hallucination probe for Two Truths and a Lie",
        modal_app_name="unified-probe-service-70b",
        gpu_type="H100",
        gpu_count=4,
        estimated_memory_gb=320,  # 4x 80GB H100s
    ),
    "instructive_pairs_8b": ProbeConfig(
        probe_name="instructive_pairs_8b",
        volume_path="repe_honesty_roleplay_Meta-Llama-3.1-8B-Instruct_linear-contrastive_layer20_l25p0",  # Path on Modal volume (was uploaded with this name)
        probe_type="hallucination",  # Similar to hallucination, detects truthfulness
        model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
        layer=20,
        description="8B instructive pairs probe (AUROC 0.7851) for truthfulness detection in poker",
        modal_app_name="unified-probe-service",
        gpu_type="A10G",
        gpu_count=1,
        estimated_memory_gb=20,
    ),
}


def get_probe_config(probe_name: str) -> ProbeConfig:
    """
    Get probe configuration by name.

    Args:
        probe_name: Name from PROBE_REGISTRY (e.g., "deception_8b")

    Returns:
        ProbeConfig instance

    Raises:
        KeyError: If probe_name not in registry
    """
    if probe_name not in PROBE_REGISTRY:
        available = ", ".join(PROBE_REGISTRY.keys())
        raise KeyError(f"Unknown probe '{probe_name}'. Available: {available}")

    return PROBE_REGISTRY[probe_name]
