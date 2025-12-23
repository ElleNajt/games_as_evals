"""
Unified Modal backend for serving LLM probes with vLLM.

Single file that creates both 8B and 70B probe services with different configs.
Each service handles all probe types (deception, hallucination, etc.) by loading
from volume paths and returning per-token activations.

Version: 3.1 - Single-file multi-model service (2025-12-21)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List

import modal

from .probe_service_shared import ProbeServiceBase, build_health_check_response

logger = logging.getLogger(__name__)

# Volume for storing models and probes (shared by all services)
VOLUME = modal.Volume.from_name("unified-probe-models", create_if_missing=False)
VOLUME_PATH = "/volume"
PROBES_DIR = Path(VOLUME_PATH) / "models" / "probes"
MODEL_CACHE_DIR = Path(VOLUME_PATH) / "models" / "huggingface"

# HuggingFace secret (shared by all services)
HF_SECRET = modal.Secret.from_name("huggingface-secret")

# Modal image (shared by all services)
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

# Model configurations
MODEL_CONFIGS = {
    "8b": {
        "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "gpu": "A10G",
        "n_gpu": 1,
        "timeout": 20 * 60,  # 20 minutes
        "scaledown_window": 2 * 60,  # 2 minutes
    },
    "70b": {
        "model": "meta-llama/Meta-Llama-3.1-70B-Instruct",
        "gpu": modal.gpu.H100(count=4),
        "n_gpu": 4,
        "timeout": 30 * 60,  # 30 minutes
        "scaledown_window": 2 * 60,  # 2 minutes
    },
}


def create_probe_service(model_size: str):
    """
    Factory function to create a probe service for a given model size.

    Args:
        model_size: "8b" or "70b"

    Returns:
        (app, service_class): Modal app and UnifiedProbeService class
    """
    if model_size not in MODEL_CONFIGS:
        raise ValueError(
            f"Unknown model size '{model_size}'. Available: {list(MODEL_CONFIGS.keys())}"
        )

    config = MODEL_CONFIGS[model_size]
    app_name = (
        f"unified-probe-service"
        if model_size == "8b"
        else f"unified-probe-service-{model_size}"
    )

    app = modal.App(app_name, image=image)

    @app.cls(
        image=image,
        gpu=config["gpu"],
        container_idle_timeout=config["scaledown_window"],
        volumes={VOLUME_PATH: VOLUME},
        timeout=config["timeout"],
        secrets=[HF_SECRET],
    )
    class UnifiedProbeService(ProbeServiceBase):
        """
        Probe service for {model_size.upper()} model.

        Inherits all logic from ProbeServiceBase, configures model-specific parameters.
        """

        model_name: str = modal.parameter(default=config["model"])
        n_gpu: int = config["n_gpu"]
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
        return build_health_check_response(app_name)

    # Add download helper for 70B model
    if model_size == "70b":

        @app.function(
            image=image,
            volumes={VOLUME_PATH: VOLUME},
            secrets=[HF_SECRET],
            timeout=3600,  # 1 hour for download
        )
        def download_model_to_volume(model_name: str = config["model"]):
            """
            Download model to volume once for caching.

            Run this once with: modal run unified_probe_service.py::download_model_to_volume_70b
            """
            import os

            from huggingface_hub import snapshot_download

            cache_dir = MODEL_CACHE_DIR / model_name.replace("/", "--")
            cache_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Downloading {model_name} to {cache_dir}...")
            logger.info(f"This will take ~10-15 minutes for 70B model (~140GB)")

            snapshot_download(
                repo_id=model_name,
                local_dir=str(cache_dir),
                local_dir_use_symlinks=False,
                token=os.environ.get("HF_TOKEN"),
            )

            # Commit volume changes
            VOLUME.commit()
            logger.info(f"✓ Model cached at {cache_dir}")
            logger.info(
                f"Volume committed. Model will be available for all future deployments."
            )

            return str(cache_dir)

        # Expose download function with model-specific name
        app.function_map[f"download_model_to_volume_{model_size}"] = (
            download_model_to_volume
        )

    return app, UnifiedProbeService


# Create both services
app_8b, Service8B = create_probe_service("8b")
app_70b, Service70B = create_probe_service("70b")

# Export the 8B app as default for backward compatibility
app = app_8b


if __name__ == "__main__":
    # Test locally
    print("Available apps: app_8b, app_70b")
    print("Available services: Service8B, Service70B")
    print("\nTo deploy:")
    print("  modal deploy unified_probe_service.py::app_8b")
    print("  modal deploy unified_probe_service.py::app_70b")
