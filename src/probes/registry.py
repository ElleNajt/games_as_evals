"""Probe registry for deception and hallucination probes."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProbeConfig:
    """Configuration for an activation probe."""
    
    probe_id: str
    """Probe identifier (e.g., 'llama3_1_8b_lora_lambda_kl=0.5')"""
    
    probe_type: str
    """Type of probe: 'deception' or 'hallucination'"""
    
    model_name: str
    """Compatible model (e.g., 'meta-llama/Meta-Llama-3.1-8B-Instruct')"""
    
    layer: int
    """Which model layer to probe (e.g., 22 for roleplaying deception)"""
    
    modal_app_name: str
    """Modal deployment name"""
    
    repo_id: Optional[str] = None
    """HuggingFace repo ID (e.g., 'andyrdt/hallucination-probes')"""
    
    description: str = ""
    """Human-readable description"""
    
    # GPU requirements (informational - actual allocation happens in Modal deployment)
    gpu_type: str = "A10G"
    """GPU type required (e.g., 'A10G', 'H100')"""
    
    gpu_count: int = 1
    """Number of GPUs required"""
    
    estimated_memory_gb: int = 24
    """Estimated GPU memory usage in GB"""


# Registry of available probes
PROBE_REGISTRY = {
    "deception_8b": ProbeConfig(
        probe_id="llama3_1_8b_lora_lambda_kl=0.5",
        probe_type="deception",
        model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
        layer=22,
        modal_app_name="werewolf-apollo-probe",  # From werewolf repo
        repo_id=None,  # Uses Apollo detector from local file
        description="8B deception probe (Apollo roleplaying) for Werewolf/3-SAT",
        gpu_type="A10G",
        gpu_count=1,
        estimated_memory_gb=20
    ),
    
    "deception_70b": ProbeConfig(
        probe_id="llama3_70b_roleplaying",
        probe_type="deception",
        model_name="meta-llama/Llama-3.3-70B-Instruct",
        layer=22,
        modal_app_name="werewolf-apollo-probe-70b",  # From werewolf repo
        repo_id=None,  # Uses Apollo detector from local file
        description="70B deception probe (Apollo roleplaying) for Werewolf",
        gpu_type="H100",
        gpu_count=4,
        estimated_memory_gb=320  # 4x 80GB H100s
    ),
    
    "hallucination_8b": ProbeConfig(
        probe_id="llama3_1_8b_lora_lambda_kl=0.5",
        probe_type="hallucination",
        model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
        layer=30,  # Layer 30 from TTLGame probe config
        modal_app_name="hallucination-probe-backend",  # From TTLGame repo
        repo_id="andyrdt/hallucination-probes",
        description="8B hallucination probe for Two Truths and a Lie",
        gpu_type="A10G",
        gpu_count=1,
        estimated_memory_gb=20
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
