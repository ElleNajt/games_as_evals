"""
Unified Modal backend for serving 70B LLM probes with vLLM.

70B model deployment requiring 4x H100 GPUs.
Version: 3.0 - Unified with 8B service via shared base class (2025-12-21)
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import modal

from .probe_service_shared import ProbeServiceBase, build_health_check_response

logger = logging.getLogger(__name__)

# Configuration for 70B model
DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct"
N_GPU = 4
GPU_CONFIG = modal.gpu.H100(count=4)
SCALEDOWN_WINDOW = 2 * 60
TIMEOUT = 30 * 60

# Volume configuration
VOLUME = modal.Volume.from_name("unified-probe-models", create_if_missing=False)
VOLUME_PATH = "/volume"
PROBES_DIR = Path(VOLUME_PATH) / "models" / "probes"
MODEL_CACHE_DIR = Path(VOLUME_PATH) / "models" / "huggingface"

# HuggingFace secret
HF_SECRET = modal.Secret.from_name("huggingface-secret")

# Modal image
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch>=2.0.0",
    "transformers>=4.40.0",
    "accelerate>=0.20.0",
    "numpy>=1.24.0",
    "vllm==0.6.3",
    "huggingface_hub>=0.20.0",
    "scikit-learn>=1.3.0",
    "jaxtyping>=0.2.0",
)

app = modal.App("unified-probe-service-70b", image=image)


@app.function(image=image, volumes={VOLUME_PATH: VOLUME}, secrets=[HF_SECRET], timeout=3600)
def download_model_to_volume(model_name: str = DEFAULT_MODEL):
    """Download model to volume for caching."""
    from huggingface_hub import snapshot_download

    cache_dir = MODEL_CACHE_DIR / model_name.replace("/", "--")
    cache_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Downloading {model_name}...")
    snapshot_download(
        repo_id=model_name,
        local_dir=str(cache_dir),
        local_dir_use_symlinks=False,
        token=os.environ.get("HF_TOKEN"),
    )

    VOLUME.commit()
    logger.info(f"✓ Model cached")
    return str(cache_dir)


@app.cls(
    image=image,
    gpu=GPU_CONFIG,
    container_idle_timeout=SCALEDOWN_WINDOW,
    volumes={VOLUME_PATH: VOLUME},
    timeout=TIMEOUT,
    secrets=[HF_SECRET],
)
class UnifiedProbeService(ProbeServiceBase):
    """70B model probe service - inherits all logic from ProbeServiceBase."""

    model_name: str = modal.parameter(default=DEFAULT_MODEL)
    n_gpu: int = N_GPU
    volume_path: str = VOLUME_PATH

    @modal.enter()
    def load_model(self):
        super().load_model()

    @modal.method()
    def generate_with_probe(self, messages: List[Dict[str, str]], probe_path: str, 
                           max_tokens: int = 512, temperature: float = 0.7, top_k_logits: int = 0) -> Dict[str, Any]:
        return self._generate_with_probe_impl(messages, probe_path, max_tokens, temperature, top_k_logits)

    @modal.method()
    def generate_with_probes(self, messages: List[Dict[str, str]], probe_paths: Dict[str, str],
                            max_tokens: int = 512, temperature: float = 0.7, top_k_logits: int = 0) -> Dict[str, Any]:
        return self._generate_with_probes_impl(messages, probe_paths, max_tokens, temperature, top_k_logits)

    @modal.method()
    def generate(self, messages: List[Dict[str, str]], max_tokens: int = 512, temperature: float = 0.7) -> Dict[str, Any]:
        return self._generate_impl(messages, max_tokens, temperature)

    @modal.method()
    def generate_without_probe(self, messages: List[Dict[str, str]], max_tokens: int = 512, temperature: float = 0.7) -> Dict[str, Any]:
        return self.generate(messages, max_tokens, temperature)


@app.function(image=image, volumes={VOLUME_PATH: VOLUME})
def health_check():
    return build_health_check_response("unified-probe-service-70b")
