"""Training configuration for probe training."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class TrainingConfig:
    """Configuration for probe training.
    
    Attributes:
        dataset_name: Name of the dataset (e.g., "roleplaying", "truthfulqa")
        model: Model name (e.g., "meta-llama/Meta-Llama-3.1-8B-Instruct")
        method: Training method name (e.g., "linear-contrastive", "massmean")
        layer: Layer number to extract activations from
        learning_rate: Learning rate for gradient-based methods
        num_epochs: Number of training epochs
        batch_size: Batch size for training
        val_split: Validation split ratio (0.0-1.0)
        seed: Random seed for reproducibility
        device: Device to train on ("cuda" or "cpu")
        additional_params: Method-specific additional parameters
    """
    dataset_name: str
    model: str
    method: str
    layer: int
    
    # Training hyperparameters
    learning_rate: float = 1e-3
    num_epochs: int = 10
    batch_size: int = 32
    val_split: float = 0.2
    seed: int = 42
    device: str = "cuda"
    
    # Method-specific parameters
    additional_params: Dict[str, Any] = field(default_factory=dict)
    
    def generate_probe_name(self) -> str:
        """Generate probe name from config.
        
        Format: {dataset}-{model_abbrev}-{method}
        Example: roleplaying-llama8b-linear-contrastive
        """
        model_abbrev = self._standardize_model_name(self.model)
        return f"{self.dataset_name}-{model_abbrev}-{self.method}"
    
    @staticmethod
    def _standardize_model_name(model: str) -> str:
        """Standardize model name to short abbreviation.
        
        Examples:
            meta-llama/Meta-Llama-3.1-8B-Instruct -> llama8b
            meta-llama/Llama-3.3-70B-Instruct -> llama70b
        """
        model_lower = model.lower()
        
        if "8b" in model_lower:
            return "llama8b"
        elif "70b" in model_lower:
            return "llama70b"
        else:
            # Fallback: extract size if possible
            import re
            match = re.search(r'(\d+)b', model_lower)
            if match:
                size = match.group(1)
                return f"llama{size}b"
            return "unknown"
