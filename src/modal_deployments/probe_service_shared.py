"""
Shared code for Modal probe services (8B and 70B).

This module contains common functionality used by both unified_probe_service.py
and unified_probe_service_70b.py to reduce code duplication.
"""

import json
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


def load_probe_from_volume(probe_path: Path):
    """
    Load a probe from the volume.

    Supports two formats:
    1. Apollo format: probe_head.pt with metadata (pickle)
    2. Hallucination format: probe_head.bin + probe_config.json

    Args:
        probe_path: Path to probe directory on volume

    Returns:
        (probe_head, layer_idx)
    """
    import pickle

    import torch
    import torch.nn as nn

    # Check for Apollo format first (.pt file)
    apollo_file = probe_path / "probe_detector.pt"
    if apollo_file.exists():
        logger.info(f"Loading Apollo format probe from {probe_path}")
        with open(apollo_file, "rb") as f:
            data = pickle.load(f)

        # Convert numpy arrays to tensors if needed
        import numpy as np

        def ensure_tensor(obj):
            if isinstance(obj, np.ndarray):
                return torch.from_numpy(obj)
            elif isinstance(obj, dict):
                return {k: ensure_tensor(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [ensure_tensor(item) for item in obj]
            return obj

        data = ensure_tensor(data)

        # Extract probe info
        layers = data["layers"]
        layer_idx = layers[0] if isinstance(layers, list) else layers
        directions = data["directions"]
        direction = (
            directions[layer_idx] if isinstance(directions, dict) else directions
        )

        # Create linear probe head
        hidden_dim = direction.shape[-1]
        probe_head = nn.Linear(hidden_dim, 1, bias=False)

        # Load weights (direction is the weight)
        with torch.no_grad():
            probe_head.weight.copy_(direction.view(1, -1))

        return probe_head, layer_idx

    # Check for hallucination format
    config_file = probe_path / "probe_config.json"
    weights_file = probe_path / "probe_head.bin"

    if config_file.exists() and weights_file.exists():
        logger.info(f"Loading hallucination format probe from {probe_path}")

        # Load config
        with open(config_file) as f:
            config = json.load(f)

        hidden_size = config["hidden_size"]
        layer_idx = config["layer_idx"]

        # Create probe head
        probe_head = nn.Linear(hidden_size, 1, device="cpu", dtype=torch.float32)

        # Load weights
        state_dict = torch.load(weights_file, map_location="cpu", weights_only=True)
        probe_head.load_state_dict(state_dict)
        probe_head.eval()

        return probe_head, layer_idx

    raise ValueError(
        f"No valid probe found at {probe_path}. Expected probe_detector.pt or probe_head.bin+probe_config.json"
    )


def load_probe_if_needed(probe_path: str, loaded_probes: dict):
    """
    Load probe from volume if not already cached.

    Args:
        probe_path: Path to probe directory. Can be:
            - Absolute path (e.g., "/volume/models/probes/deception_8b_layer12")
            - Relative to /volume/models/probes/ (e.g., "deception_8b_layer12")
        loaded_probes: Dictionary of already loaded probes to check/update

    Returns:
        (probe_head, layer_idx): The probe head module and target layer index

    Note: Relative paths are ALWAYS relative to /volume/models/probes/, not /volume/models/.
    So "deception_8b" becomes "/volume/models/probes/deception_8b", not "/volume/models/deception_8b".
    """
    import torch

    if probe_path not in loaded_probes:
        path = Path(probe_path)
        if not path.is_absolute():
            # Make relative paths relative to /volume/models/probes/
            path = Path("/volume/models/probes") / path

        probe_head, layer_idx = load_probe_from_volume(path)

        # Move to GPU and convert to bfloat16 to match vLLM model dtype
        probe_head = probe_head.to(device="cuda", dtype=torch.bfloat16)
        probe_head.eval()

        loaded_probes[probe_path] = (probe_head, layer_idx)
        logger.info(f"Loaded probe from {path} (layer {layer_idx})")

    return loaded_probes[probe_path]


def build_health_check_response(service_name: str):
    """
    Build health check response by inspecting volume contents.

    Args:
        service_name: Name of the service for the response

    Returns:
        Dict with health status and probe/volume information
    """
    from pathlib import Path

    # Check what's in the volume
    probes_dir = Path("/volume/models/probes")
    if probes_dir.exists():
        probe_files = {}
        for item in probes_dir.iterdir():
            if item.is_dir():
                probe_files[str(item)] = list(str(f) for f in item.iterdir())
        return {
            "status": "healthy",
            "service": service_name,
            "probes": probe_files,
        }
    else:
        # Check what's at volume root for debugging
        vol_root = Path("/volume")
        if vol_root.exists():
            root_contents = list(str(f) for f in vol_root.iterdir())
            return {
                "status": "healthy",
                "service": service_name,
                "error": "probes not found",
                "volume_root": root_contents,
            }
        else:
            return {
                "status": "healthy",
                "service": service_name,
                "error": "/volume not mounted",
            }
