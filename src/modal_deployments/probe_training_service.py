"""Modal service for distributed probe training on GPUs.

This service allows training probes on Modal's GPU infrastructure with:
- Automatic model downloading from HuggingFace
- Dataset loading from volume or repo
- Multiple training methods (massmean, linear-contrastive, LDA, LAT)
- Probe saving to volume for later use

All training code is self-contained to avoid dependency issues.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import modal

# Configuration
GPU_CONFIG_8B = "A10G"  # For 8B models
GPU_CONFIG_70B = "H100"  # For 70B models
TIMEOUT = 60 * 60  # 1 hour timeout for training

# Volume for storing probes and datasets
VOLUME = modal.Volume.from_name("unified-probe-models", create_if_missing=False)
VOLUME_PATH = "/volume"

# HuggingFace secret for model downloads
HF_SECRET = modal.Secret.from_name("huggingface-secret")

# Modal image with all dependencies
image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "torch>=2.0.0",
    "transformers>=4.40.0",
    "accelerate>=0.20.0",
    "numpy>=1.24.0",
    "huggingface_hub>=0.20.0",
    "scikit-learn>=1.3.0",
    "jaxtyping>=0.2.0",
    "einops>=0.7.0",
    "pyyaml>=6.0",
)

app = modal.App("probe-training-service", image=image)


@app.function(
    gpu=GPU_CONFIG_8B,
    timeout=TIMEOUT,
    secrets=[HF_SECRET],
    volumes={VOLUME_PATH: VOLUME},
)
def train_probe_on_modal(
    dataset_name: str,
    model_name: str,
    method: str,
    layer: int,
    learning_rate: float = 1e-3,
    num_epochs: int = 10,
    batch_size: int = 8,
    seed: int = 42,
) -> Dict[str, Any]:
    """Train a probe on Modal with GPU acceleration.

    Args:
        dataset_name: Name of dataset (e.g., "roleplaying")
        model_name: HuggingFace model name
        method: Training method (massmean, linear-contrastive, lda, lat)
        layer: Which layer to extract activations from
        learning_rate: Learning rate for gradient-based methods
        num_epochs: Number of training epochs
        batch_size: Batch size for activation extraction
        seed: Random seed

    Returns:
        Dictionary with probe_name, metrics, and volume path
    """
    from dataclasses import dataclass
    from typing import List, Tuple

    import einops
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from transformers import AutoModelForCausalLM, AutoTokenizer

    # --- Inline Data Structures ---

    @dataclass
    class ContrastivePair:
        positive: str
        negative: str
        metadata: Optional[Dict] = None

    @dataclass
    class ActivationData:
        positive_acts: torch.Tensor
        negative_acts: torch.Tensor

    # --- Inline Model Loading ---

    def load_model_and_tokenizer(model_name: str, device: str = "cuda"):
        """Load model and tokenizer from HuggingFace."""
        print(f"Loading model: {model_name}")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16,
            device_map=device,
            trust_remote_code=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(model_name)

        # Set padding token if not set
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model.eval()
        return model, tokenizer

    # --- Inline Activation Extraction ---

    def extract_activations_from_text(
        model,
        tokenizer,
        texts: List[str],
        layer: int,
        batch_size: int = 8,
        device: str = "cuda",
        verbose: bool = True,
    ):
        """Extract activations from a list of texts."""
        all_activations = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]

            # Tokenize
            inputs = tokenizer(
                batch_texts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            ).to(device)

            # Extract activations
            with torch.no_grad():
                outputs = model(**inputs, output_hidden_states=True)
                hidden_states = outputs.hidden_states[
                    layer
                ]  # [batch, seq_len, hidden_dim]

                # Take last token activation for each example
                last_token_acts = hidden_states[:, -1, :]  # [batch, hidden_dim]
                all_activations.append(last_token_acts.cpu())

        return torch.cat(all_activations, dim=0)  # [n_examples, hidden_dim]

    def extract_contrastive_activations(
        model,
        tokenizer,
        dataset_pairs: List[ContrastivePair],
        layer: int,
        batch_size: int = 8,
        device: str = "cuda",
        verbose: bool = True,
    ):
        """Extract activations for positive and negative examples."""
        positive_texts = [pair.positive for pair in dataset_pairs]
        negative_texts = [pair.negative for pair in dataset_pairs]

        if verbose:
            print(
                f"  Extracting activations for {len(positive_texts)} positive examples..."
            )
        pos_acts = extract_activations_from_text(
            model, tokenizer, positive_texts, layer, batch_size, device, verbose=False
        )

        if verbose:
            print(
                f"  Extracting activations for {len(negative_texts)} negative examples..."
            )
        neg_acts = extract_activations_from_text(
            model, tokenizer, negative_texts, layer, batch_size, device, verbose=False
        )

        return ActivationData(positive_acts=pos_acts, negative_acts=neg_acts)

    # --- Inline Training Methods ---

    def train_massmean(activation_data: ActivationData):
        """Train mass-mean probe (difference of means)."""
        pos_acts = activation_data.positive_acts
        neg_acts = activation_data.negative_acts

        # Compute mean activations
        pos_mean = pos_acts.mean(dim=0)
        neg_mean = neg_acts.mean(dim=0)

        # Direction is difference of means
        direction = pos_mean - neg_mean
        direction = direction / (direction.norm() + 1e-8)

        # Compute metrics
        with torch.no_grad():
            pos_scores = pos_acts @ direction
            neg_scores = neg_acts @ direction

            correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
            total = len(pos_scores) + len(neg_scores)
            accuracy = (correct.float() / total).item()

        metrics = {
            "accuracy": accuracy,
            "mean_pos_score": pos_scores.mean().item(),
            "mean_neg_score": neg_scores.mean().item(),
            "separation": (pos_scores.mean() - neg_scores.mean()).item(),
        }

        return direction, metrics

    def train_linear_contrastive(
        activation_data: ActivationData, learning_rate: float, num_epochs: int
    ):
        """Train linear probe with contrastive loss."""
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        pos_acts = activation_data.positive_acts.to(device).to(torch.float32)
        neg_acts = activation_data.negative_acts.to(device).to(torch.float32)

        hidden_dim = pos_acts.shape[1]

        # Initialize probe direction
        direction = nn.Parameter(
            torch.randn(hidden_dim, device=device, dtype=torch.float32)
        )
        optimizer = optim.Adam([direction], lr=learning_rate)

        best_loss = float("inf")
        best_direction = None

        for epoch in range(num_epochs):
            optimizer.zero_grad()

            # Normalize direction
            norm_direction = direction / (direction.norm() + 1e-8)

            # Compute scores
            pos_scores = pos_acts @ norm_direction
            neg_scores = neg_acts @ norm_direction

            # Contrastive loss
            loss = -pos_scores.mean() + neg_scores.mean()

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

            correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
            total = len(pos_scores) + len(neg_scores)
            accuracy = (correct.float() / total).item()

        metrics = {
            "final_loss": best_loss,
            "accuracy": accuracy,
            "mean_pos_score": pos_scores.mean().item(),
            "mean_neg_score": neg_scores.mean().item(),
        }

        return final_direction.cpu(), metrics

    def train_lda(activation_data: ActivationData):
        """Train LDA (Linear Discriminant Analysis) probe."""
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float32

        pos_acts = activation_data.positive_acts.to(device).to(dtype)
        neg_acts = activation_data.negative_acts.to(device).to(dtype)

        # Compute mean difference
        pos_mean = pos_acts.mean(dim=0)
        neg_mean = neg_acts.mean(dim=0)
        mean_diff = pos_mean - neg_mean

        # Compute covariance matrices
        pos_cov = torch.cov(pos_acts.T, correction=0)
        neg_cov = torch.cov(neg_acts.T, correction=0)

        # Average covariance
        cov_matrix = (pos_cov + neg_cov) / 2

        # Fisher's Linear Discriminant
        cov_inv = torch.linalg.pinv(cov_matrix)
        direction = cov_inv @ mean_diff
        direction = direction / (direction.norm() + 1e-8)

        # Compute metrics
        with torch.no_grad():
            pos_scores = pos_acts @ direction
            neg_scores = neg_acts @ direction

            correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
            total = len(pos_scores) + len(neg_scores)
            accuracy = (correct.float() / total).item()

        metrics = {
            "accuracy": accuracy,
            "mean_pos_score": pos_scores.mean().item(),
            "mean_neg_score": neg_scores.mean().item(),
            "separation": (pos_scores.mean() - neg_scores.mean()).item(),
        }

        return direction.cpu(), metrics

    def train_lat(activation_data: ActivationData, seed: int):
        """Train LAT (Linear Artificial Tomography) probe."""
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        dtype = torch.float32

        pos_acts = activation_data.positive_acts.to(device).to(dtype)
        neg_acts = activation_data.negative_acts.to(device).to(dtype)

        # Compute difference vectors
        diffs = pos_acts - neg_acts

        # Randomly flip signs
        torch.manual_seed(seed)
        signs = torch.where(torch.randn(len(diffs), device=device) > 0, 1, -1)
        diffs *= signs[:, None]

        # Find first PCA component
        _, _, V = torch.pca_lowrank(diffs, q=1, center=True)
        direction = V[:, 0]

        # Ensure direction points in positive direction
        pos_scores = pos_acts @ direction
        neg_scores = neg_acts @ direction

        if pos_scores.mean() < neg_scores.mean():
            direction = -direction

        # Compute metrics
        with torch.no_grad():
            pos_scores = pos_acts @ direction
            neg_scores = neg_acts @ direction

            correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
            total = len(pos_scores) + len(neg_scores)
            accuracy = (correct.float() / total).item()

        metrics = {
            "accuracy": accuracy,
            "mean_pos_score": pos_scores.mean().item(),
            "mean_neg_score": neg_scores.mean().item(),
            "separation": (pos_scores.mean() - neg_scores.mean()).item(),
        }

        return direction.cpu(), metrics

    # --- Main Training Pipeline ---

    print("=" * 70)
    print("Modal Probe Training")
    print("=" * 70)
    print(f"Dataset: {dataset_name}")
    print(f"Model: {model_name}")
    print(f"Method: {method}")
    print(f"Layer: {layer}")
    print(f"Device: cuda")
    print("=" * 70)
    print()

    # Generate probe name
    probe_name = f"{dataset_name}_{model_name.split('/')[-1]}_{method}_layer{layer}"

    # Step 1: Load dataset from volume
    print("Step 1/4: Loading dataset from volume...")

    dataset_path = Path(VOLUME_PATH) / "datasets" / dataset_name

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found on volume: {dataset_path}\n"
            f"Please upload dataset to volume first."
        )

    # Load training dataset
    train_file = dataset_path / "train.jsonl"
    train_data = []
    with open(train_file, "r") as f:
        for line in f:
            data = json.loads(line)
            train_data.append(
                ContrastivePair(
                    positive=data["positive"],
                    negative=data["negative"],
                    metadata=data.get("metadata"),
                )
            )

    # Load validation dataset
    val_file = dataset_path / "val.jsonl"
    val_data = []
    if val_file.exists():
        with open(val_file, "r") as f:
            for line in f:
                data = json.loads(line)
                val_data.append(
                    ContrastivePair(
                        positive=data["positive"],
                        negative=data["negative"],
                        metadata=data.get("metadata"),
                    )
                )

    print(f"  ✓ Loaded {len(train_data)} training examples")
    if val_data:
        print(f"  ✓ Loaded {len(val_data)} validation examples")
    print()

    # Step 2: Load model and extract activations
    print(f"Step 2/4: Loading model and extracting activations...")
    model, tokenizer = load_model_and_tokenizer(model_name, device="cuda")

    print("  Extracting training activations...")
    train_activation_data = extract_contrastive_activations(
        model=model,
        tokenizer=tokenizer,
        dataset_pairs=train_data,
        layer=layer,
        batch_size=batch_size,
        device="cuda",
        verbose=True,
    )
    print(
        f"  ✓ Extracted training activations: {train_activation_data.positive_acts.shape}"
    )

    # Extract validation activations if validation data exists
    val_activation_data = None
    if val_data:
        print("  Extracting validation activations...")
        val_activation_data = extract_contrastive_activations(
            model=model,
            tokenizer=tokenizer,
            dataset_pairs=val_data,
            layer=layer,
            batch_size=batch_size,
            device="cuda",
            verbose=False,
        )
        print(
            f"  ✓ Extracted validation activations: {val_activation_data.positive_acts.shape}"
        )
    print()

    # Free memory
    del model
    torch.cuda.empty_cache()

    # Step 3: Train probe
    print(f"Step 3/4: Training probe with {method}...")

    if method == "massmean":
        probe_weights, train_metrics = train_massmean(train_activation_data)
    elif method == "linear-contrastive":
        probe_weights, train_metrics = train_linear_contrastive(
            train_activation_data, learning_rate, num_epochs
        )
    elif method == "lda":
        probe_weights, train_metrics = train_lda(train_activation_data)
    elif method == "lat":
        probe_weights, train_metrics = train_lat(train_activation_data, seed)
    else:
        raise ValueError(f"Unknown method: {method}")

    print(f"  ✓ Training complete!")
    print(f"  Train Metrics:")
    for key, value in train_metrics.items():
        print(f"    - {key}: {value:.4f}")

    # Evaluate on validation set if available
    val_metrics = None
    if val_activation_data is not None:
        print(f"  Evaluating on validation set...")
        with torch.no_grad():
            pos_scores = val_activation_data.positive_acts @ probe_weights
            neg_scores = val_activation_data.negative_acts @ probe_weights

            correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
            total = len(pos_scores) + len(neg_scores)
            accuracy = (correct.float() / total).item()

        val_metrics = {
            "accuracy": accuracy,
            "mean_pos_score": pos_scores.mean().item(),
            "mean_neg_score": neg_scores.mean().item(),
            "separation": (pos_scores.mean() - neg_scores.mean()).item(),
        }
        print(f"  Val Metrics:")
        for key, value in val_metrics.items():
            print(f"    - {key}: {value:.4f}")
    print()

    # Step 4: Save probe to volume
    print("Step 4/4: Saving probe to volume...")

    probe_dir = Path(VOLUME_PATH) / "models" / "probes" / probe_name
    probe_dir.mkdir(parents=True, exist_ok=True)

    # Save probe weights with correct filename and format for inference service
    # Inference expects state_dict format: {'weight': tensor, 'bias': tensor}
    probe_state_dict = {
        "weight": probe_weights.unsqueeze(
            0
        ),  # Add batch dimension: [hidden_size] -> [1, hidden_size]
        "bias": torch.zeros(1),  # Massmean probe has no bias
    }
    probe_path = probe_dir / "probe_head.bin"
    torch.save(probe_state_dict, probe_path)

    # Save config in the format expected by inference service
    probe_config_data = {
        "hidden_size": 4096,  # Meta-Llama-3.1-8B hidden size
        "layer_idx": layer,
        "probe_type": f"{method}_probe",
        "source_model": model_name,
        "source_dataset": dataset_name,
    }

    with open(probe_dir / "probe_config.json", "w") as f:
        json.dump(probe_config_data, f, indent=2)

    # Also save training metadata separately
    training_metadata = {
        "dataset": dataset_name,
        "model": model_name,
        "method": method,
        "layer": layer,
        "train_metrics": train_metrics,
        "val_metrics": val_metrics,
        "probe_name": probe_name,
    }

    with open(probe_dir / "training_metadata.json", "w") as f:
        json.dump(training_metadata, f, indent=2)

    # Commit volume changes
    VOLUME.commit()

    print(f"  ✓ Saved to volume: {probe_dir}")
    print()
    print("=" * 70)
    print("✓✓✓ TRAINING COMPLETE! ✓✓✓")
    print("=" * 70)

    return {
        "probe_name": probe_name,
        "train_metrics": train_metrics,
        "val_metrics": val_metrics,
        "volume_path": str(probe_dir),
        "success": True,
    }


@app.function(
    volumes={VOLUME_PATH: VOLUME},
)
def download_probe_from_volume(probe_name: str, modal_path: str, local_path: str):
    """Download a trained probe from Modal volume to local machine.

    Args:
        probe_name: Name of the probe
        modal_path: Path on Modal volume (e.g., /volume/models/probes/probe_name)
        local_path: Local path to save probe file
    """
    from pathlib import Path

    print(f"Downloading probe '{probe_name}' from Modal volume...")

    # Read probe file from volume (correct filename)
    volume_probe_path = Path(modal_path) / "probe_head.bin"

    if not volume_probe_path.exists():
        raise FileNotFoundError(f"Probe not found on volume: {volume_probe_path}")

    # Read the probe file
    with open(volume_probe_path, "rb") as f:
        probe_data = f.read()

    print(f"  ✓ Read probe from volume: {len(probe_data)} bytes")

    # Return the data (Modal will handle sending it back)
    return probe_data


@app.function(
    volumes={VOLUME_PATH: VOLUME},
)
def upload_dataset_files(dataset_name: str, files_data: Dict[str, str]):
    """Upload dataset files to Modal volume.

    Args:
        dataset_name: Name for the dataset
        files_data: Dictionary of {filename: file_content}
    """
    from pathlib import Path

    print(f"Uploading dataset '{dataset_name}' to volume...")

    # Create dataset directory on volume
    volume_dataset_path = Path(VOLUME_PATH) / "datasets" / dataset_name
    volume_dataset_path.mkdir(parents=True, exist_ok=True)

    # Write each file
    for filename, content in files_data.items():
        file_path = volume_dataset_path / filename
        with open(file_path, "w") as f:
            f.write(content)
        print(f"  ✓ Uploaded: {filename}")

    VOLUME.commit()
    print(f"  ✓ Dataset uploaded to: {volume_dataset_path}")


@app.function(
    gpu=GPU_CONFIG_8B,
    timeout=TIMEOUT * 3,  # 3 hours for layer sweep
    secrets=[HF_SECRET],
    volumes={VOLUME_PATH: VOLUME},
)
def sweep_layers_on_modal(
    dataset_name: str,
    model_name: str,
    method: str,
    layers: Optional[List[int]] = None,
    learning_rate: float = 1e-3,
    num_epochs: int = 100,
    batch_size: int = 8,
    seed: int = 42,
) -> Dict[str, Any]:
    """Sweep across layers to find best probe using AUROC.

    Args:
        dataset_name: Name of dataset (e.g., "roleplaying")
        model_name: HuggingFace model name
        method: Training method
        layers: List of layers to test (None = all layers)
        learning_rate: Learning rate for gradient-based methods
        num_epochs: Number of training epochs
        batch_size: Batch size for activation extraction
        seed: Random seed

    Returns:
        Dict with best layer, metrics, and all results
    """
    import json
    from pathlib import Path
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from dataclasses import dataclass
    from typing import List, Optional, Dict
    import numpy as np
    from sklearn.metrics import roc_auc_score

    # Inline data structures
    @dataclass
    class ContrastivePair:
        positive: str
        negative: str
        metadata: Optional[Dict] = None

    @dataclass
    class ActivationData:
        positive_acts: torch.Tensor
        negative_acts: torch.Tensor

    # Inline helper functions (copy from train_probe_on_modal)
    def load_model_and_tokenizer(model_name: str, device: str = "cuda"):
        print(f"Loading model: {model_name}")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16,
            device_map=device,
            trust_remote_code=True,
        )
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model.eval()
        return model, tokenizer

    def extract_activations_from_text(model, tokenizer, texts, layer, batch_size=8, device="cuda"):
        all_activations = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            inputs = tokenizer(batch_texts, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
            with torch.no_grad():
                outputs = model(**inputs, output_hidden_states=True)
                hidden_states = outputs.hidden_states[layer]
                last_token_acts = hidden_states[:, -1, :]
                all_activations.append(last_token_acts.cpu())
        return torch.cat(all_activations, dim=0)

    def extract_contrastive_activations(model, tokenizer, dataset_pairs, layer, batch_size=8, device="cuda"):
        positive_texts = [pair.positive for pair in dataset_pairs]
        negative_texts = [pair.negative for pair in dataset_pairs]
        pos_acts = extract_activations_from_text(model, tokenizer, positive_texts, layer, batch_size, device)
        neg_acts = extract_activations_from_text(model, tokenizer, negative_texts, layer, batch_size, device)
        return ActivationData(positive_acts=pos_acts, negative_acts=neg_acts)

    def train_linear_contrastive(activation_data, learning_rate, num_epochs):
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        pos_acts = activation_data.positive_acts.to(device).to(torch.float32)
        neg_acts = activation_data.negative_acts.to(device).to(torch.float32)
        hidden_dim = pos_acts.shape[1]

        direction = nn.Parameter(torch.randn(hidden_dim, device=device, dtype=torch.float32))
        optimizer = optim.Adam([direction], lr=learning_rate)

        best_loss = float("inf")
        best_direction = None

        for epoch in range(num_epochs):
            optimizer.zero_grad()
            norm_direction = direction / (direction.norm() + 1e-8)
            pos_scores = pos_acts @ norm_direction
            neg_scores = neg_acts @ norm_direction
            loss = -pos_scores.mean() + neg_scores.mean()
            loss.backward()
            optimizer.step()

            if loss.item() < best_loss:
                best_loss = loss.item()
                best_direction = norm_direction.detach().clone()

        with torch.no_grad():
            final_direction = best_direction / (best_direction.norm() + 1e-8)
            pos_scores = pos_acts @ final_direction
            neg_scores = neg_acts @ final_direction
            correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
            total = len(pos_scores) + len(neg_scores)
            accuracy = (correct.float() / total).item()

        metrics = {
            "accuracy": accuracy,
            "separation": (pos_scores.mean() - neg_scores.mean()).item(),
        }
        return final_direction.cpu(), metrics

    def calculate_auroc(probe_weights, positive_acts, negative_acts):
        with torch.no_grad():
            # Ensure all tensors have the same dtype (convert to float32)
            probe_weights = probe_weights.float()
            positive_acts = positive_acts.float()
            negative_acts = negative_acts.float()
            pos_scores = (positive_acts @ probe_weights).cpu().numpy()
            neg_scores = (negative_acts @ probe_weights).cpu().numpy()
        y_true = np.array([1] * len(neg_scores) + [0] * len(pos_scores))
        y_scores = np.concatenate([neg_scores, pos_scores])
        return float(roc_auc_score(y_true, y_scores))

    # Main sweep logic
    print("=" * 70)
    print("Modal Layer Sweep for Probe Training")
    print("=" * 70)
    print(f"Dataset: {dataset_name}")
    print(f"Model: {model_name}")
    print(f"Method: {method}")
    print("=" * 70)

    # Load dataset
    dataset_path = Path(VOLUME_PATH) / "datasets" / dataset_name
    train_file = dataset_path / "train.jsonl"
    val_file = dataset_path / "val.jsonl"

    train_data = []
    with open(train_file, "r") as f:
        for line in f:
            data = json.loads(line)
            train_data.append(ContrastivePair(positive=data["positive"], negative=data["negative"]))

    val_data = []
    with open(val_file, "r") as f:
        for line in f:
            data = json.loads(line)
            val_data.append(ContrastivePair(positive=data["positive"], negative=data["negative"]))

    print(f"Loaded {len(train_data)} train, {len(val_data)} val examples")

    # Load model once
    model, tokenizer = load_model_and_tokenizer(model_name, device="cuda")

    # Determine layers to sweep
    if layers is None:
        num_layers = model.config.num_hidden_layers
        layers = list(range(num_layers))

    print(f"Sweeping layers: {layers}")
    print()

    # Sweep layers
    results = []
    all_probes = {}

    for layer in layers:
        print(f"Layer {layer}:")

        # Extract activations
        print("  Extracting training activations...")
        train_acts = extract_contrastive_activations(model, tokenizer, train_data, layer, batch_size, "cuda")

        # Train probe
        print(f"  Training with {method}...")
        if method == "linear-contrastive":
            probe_weights, train_metrics = train_linear_contrastive(train_acts, learning_rate, num_epochs)
        else:
            raise ValueError(f"Method {method} not yet supported in sweep")

        # Evaluate on validation
        print("  Evaluating on validation...")
        val_acts = extract_contrastive_activations(model, tokenizer, val_data, layer, batch_size, "cuda")

        val_auroc = calculate_auroc(probe_weights, val_acts.positive_acts, val_acts.negative_acts)

        with torch.no_grad():
            # Ensure consistent dtype (convert to float32)
            probe_weights_f32 = probe_weights.float()
            pos_acts_f32 = val_acts.positive_acts.float()
            neg_acts_f32 = val_acts.negative_acts.float()

            pos_scores = pos_acts_f32 @ probe_weights_f32
            neg_scores = neg_acts_f32 @ probe_weights_f32
            correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
            total = len(pos_scores) + len(neg_scores)
            val_accuracy = (correct.float() / total).item()

        metrics = {
            'layer': layer,
            'train_accuracy': train_metrics['accuracy'],
            'train_separation': train_metrics['separation'],
            'val_accuracy': val_accuracy,
            'val_auroc': val_auroc,
        }

        print(f"  Train acc: {metrics['train_accuracy']:.4f}, Val AUROC: {val_auroc:.4f}")
        print()

        results.append(metrics)
        all_probes[layer] = probe_weights

    # Find best layer by AUROC
    results_sorted = sorted(results, key=lambda x: x['val_auroc'], reverse=True)
    best_result = results_sorted[0]
    best_layer = best_result['layer']
    best_probe = all_probes[best_layer]

    print("=" * 70)
    print("SWEEP COMPLETE!")
    print(f"Best layer: {best_layer} (AUROC: {best_result['val_auroc']:.4f})")
    print("=" * 70)

    # Save best probe
    probe_name = f"{dataset_name}_{model_name.split('/')[-1]}_{method}_layer{best_layer}"
    probe_dir = Path(VOLUME_PATH) / "models" / "probes" / probe_name
    probe_dir.mkdir(parents=True, exist_ok=True)

    probe_state_dict = {
        "weight": best_probe.unsqueeze(0),
        "bias": torch.zeros(1),
    }
    torch.save(probe_state_dict, probe_dir / "probe_head.bin")

    probe_config_data = {
        "hidden_size": 4096,
        "layer_idx": best_layer,
        "probe_type": f"{method}_probe",
        "source_model": model_name,
        "source_dataset": dataset_name,
    }
    with open(probe_dir / "probe_config.json", "w") as f:
        json.dump(probe_config_data, f, indent=2)

    sweep_metadata = {
        "dataset": dataset_name,
        "model": model_name,
        "method": method,
        "layers_tested": layers,
        "best_layer": best_layer,
        "best_metrics": best_result,
        "all_results": results,
    }
    with open(probe_dir / "layer_sweep_results.json", "w") as f:
        json.dump(sweep_metadata, f, indent=2)

    VOLUME.commit()
    print(f"Saved best probe to: {probe_dir}")

    return {
        "best_layer": best_layer,
        "best_probe_name": probe_name,
        "best_metrics": best_result,
        "all_results": results,
        "volume_path": str(probe_dir),
    }


@app.local_entrypoint()
def main(
    action: str = "train",
    dataset: str = "roleplaying",
    model: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
    method: str = "massmean",
    layer: int = 12,
    layers: str = "",
):
    """CLI entrypoint for probe training service.

    Args:
        action: Action to perform ('train', 'sweep', or 'upload')
        dataset: Dataset name
        model: Model name (for training)
        method: Training method (for training)
        layer: Layer number (for training)
        layers: Comma-separated layers for sweep (e.g., "8,10,12")
    """
    if action == "upload":
        # Upload dataset to volume
        from pathlib import Path

        print(f"Uploading dataset '{dataset}' to Modal volume...")
        workspace_root = Path.cwd()
        dataset_path = workspace_root / "datasets" / dataset

        if not dataset_path.exists():
            print(f"ERROR: Dataset not found at {dataset_path}")
            return

        # Read all files
        files_data = {}
        for file_path in dataset_path.iterdir():
            if file_path.is_file():
                print(f"  Reading {file_path.name}...")
                with open(file_path, "r") as f:
                    files_data[file_path.name] = f.read()

        print(f"  Uploading {len(files_data)} files...")
        upload_dataset_files.remote(dataset_name=dataset, files_data=files_data)
        print("✓ Dataset upload complete!")

    elif action == "train":
        # Train probe
        print("Starting probe training on Modal...")
        print()

        result = train_probe_on_modal.remote(
            dataset_name=dataset,
            model_name=model,
            method=method,
            layer=layer,
        )

        print()
        print("Training completed successfully!")
        print(f"Probe name: {result['probe_name']}")
        print(f"Train Metrics: {result['train_metrics']}")
        if result["val_metrics"]:
            print(f"Val Metrics: {result['val_metrics']}")
        print(f"Volume path: {result['volume_path']}")

    elif action == "sweep":
        # Layer sweep
        print("Starting layer sweep on Modal...")
        print()

        # Parse layers
        layer_list = None
        if layers:
            layer_list = [int(l.strip()) for l in layers.split(",")]

        result = sweep_layers_on_modal.remote(
            dataset_name=dataset,
            model_name=model,
            method=method,
            layers=layer_list,
        )

        print()
        print("=" * 70)
        print("Layer sweep completed successfully!")
        print("=" * 70)
        print(f"Best layer: {result['best_layer']}")
        print(f"Best probe: {result['best_probe_name']}")
        print(f"Best AUROC: {result['best_metrics']['val_auroc']:.4f}")
        print(f"Volume path: {result['volume_path']}")
        print()
        print("All results (sorted by AUROC):")
        sorted_results = sorted(result['all_results'], key=lambda x: x['val_auroc'], reverse=True)
        for r in sorted_results[:5]:  # Show top 5
            print(f"  Layer {r['layer']}: AUROC={r['val_auroc']:.4f}, Acc={r['val_accuracy']:.4f}")

    else:
        print(f"ERROR: Unknown action '{action}'. Use 'train', 'sweep', or 'upload'.")
