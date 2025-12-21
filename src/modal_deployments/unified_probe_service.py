"""
Unified Modal backend for serving 8B LLM probes with vLLM.

8B model deployment on single A10G GPU.
Single service that handles all probe types (deception, hallucination, etc.)
by loading from volume paths and returning per-token activations.

Version: 3.0 - Unified with 70B service via shared base class (2025-12-21)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

import modal

from .probe_service_shared import ProbeServiceBase, build_health_check_response

logger = logging.getLogger(__name__)

# Configuration for 8B model
DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"
N_GPU = 1
GPU_CONFIG = "A10G"
SCALEDOWN_WINDOW = 2 * 60  # 2 minutes
TIMEOUT = 20 * 60  # 20 minutes

# Volume for storing models and probes (shared with 70B service)
VOLUME = modal.Volume.from_name("unified-probe-models", create_if_missing=False)
VOLUME_PATH = "/volume"
PROBES_DIR = Path(VOLUME_PATH) / "models" / "probes"

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

app = modal.App("unified-probe-service", image=image)


@app.cls(
    image=image,
    gpu=GPU_CONFIG,
    container_idle_timeout=SCALEDOWN_WINDOW,
    volumes={VOLUME_PATH: VOLUME},
    timeout=TIMEOUT,
    secrets=[HF_SECRET],
)
class UnifiedProbeService(ProbeServiceBase):
    """
    8B model probe service.

    Inherits all logic from ProbeServiceBase, configures for 8B model.
    """

    model_name: str = modal.parameter(default=DEFAULT_MODEL)
    n_gpu: int = N_GPU
    volume_path: str = VOLUME_PATH

    @modal.enter()
    def load_model(self):
        """Load vLLM model on container startup."""
        super().load_model()

    @modal.method()
    def generate_with_probe(
        self,
        messages: List[Dict[str, str]],
        probe_path: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_k_logits: int = 0,
    ) -> Dict[str, Any]:
        """
        Generate text with per-token probe activations.

        Args:
            messages: Chat messages
            probe_path: Path to probe on volume
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k_logits: Number of top logits to return per token (0 = disabled)

        Returns:
            Dict with generated_text, tokens, scores, etc.
        """
        return self._generate_with_probe_impl(
            messages, probe_path, max_tokens, temperature, top_k_logits
        )

    @modal.method()
    def generate_with_probes(
        self,
        messages: List[Dict[str, str]],
        probe_paths: Dict[str, str],
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_k_logits: int = 0,
    ) -> Dict[str, Any]:
        """
        Generate text with multiple probe activations in a SINGLE generation run.

        Args:
            messages: Chat messages
            probe_paths: Dict mapping probe names to volume paths
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k_logits: Number of top logits to return per token (0 = disabled)

        Returns:
            Dict with generated_text, tokens, and probe_results
        """
        return self._generate_with_probes_impl(
            messages, probe_paths, max_tokens, temperature, top_k_logits
        )

    @modal.method()
    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Generate without probe scoring (faster)."""
        return self._generate_impl(messages, max_tokens, temperature)

    @modal.method()
    def generate_without_probe(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Generate without probe scoring. Alias for backward compatibility."""
        return self.generate(messages, max_tokens, temperature)


@app.function(image=image, volumes={VOLUME_PATH: VOLUME})
def health_check():
    """Health check endpoint."""
    return build_health_check_response("unified-probe-service")


if __name__ == "__main__":
    # Test locally
    with app.run():
        service = UnifiedProbeService()
        result = service.generate_with_probe.remote(
            messages=[{"role": "user", "content": "Say hello!"}],
            probe_path="deception_8b_layer12",
            max_tokens=10,
        )
        print(result)
