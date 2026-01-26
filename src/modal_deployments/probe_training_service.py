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
    additional_params: str = "",  # Changed from Optional[Dict[str, Any]] to str for Modal CLI compatibility
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
    import json

    # Parse string parameter into dict for Modal CLI compatibility
    if additional_params:
        additional_params_dict = json.loads(additional_params) if isinstance(additional_params, str) else additional_params
    else:
        additional_params_dict = {}
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
        use_all_tokens: bool = True,
        exclude_last_n_tokens: int = 0,
    ):
        """Extract activations from a list of texts.

        Args:
            use_all_tokens: If True, use mean of all tokens (Apollo's approach)
            exclude_last_n_tokens: Number of tokens to exclude from end (for REPE)
        """
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

                if use_all_tokens:
                    # Use mean of all response tokens (Apollo's approach)
                    attention_mask = inputs.attention_mask.unsqueeze(-1).float()

                    # Exclude last N tokens if specified (for REPE dataset)
                    if exclude_last_n_tokens > 0:
                        batch_size_local, seq_len, hidden_dim = hidden_states.shape
                        for j in range(batch_size_local):
                            # Find last valid token position
                            last_pos = attention_mask[j, :, 0].sum().long() - 1
                            # Zero out the last N tokens
                            start_exclude = max(0, last_pos - exclude_last_n_tokens + 1)
                            attention_mask[j, start_exclude:last_pos+1, :] = 0

                    # Compute masked mean
                    masked_hidden_states = hidden_states * attention_mask
                    token_counts = attention_mask.sum(dim=1).clamp(min=1)
                    mean_activations = masked_hidden_states.sum(dim=1) / token_counts
                    all_activations.append(mean_activations.cpu())
                else:
                    # Take last token activation for each example (legacy)
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
        use_all_tokens: bool = True,
        exclude_last_n_tokens: int = 0,
    ):
        """Extract activations for positive and negative examples."""
        positive_texts = [pair.positive for pair in dataset_pairs]
        negative_texts = [pair.negative for pair in dataset_pairs]

        if verbose:
            print(
                f"  Extracting activations for {len(positive_texts)} positive examples..."
            )
        pos_acts = extract_activations_from_text(
            model, tokenizer, positive_texts, layer, batch_size, device, verbose=False,
            use_all_tokens=use_all_tokens, exclude_last_n_tokens=exclude_last_n_tokens
        )

        if verbose:
            print(
                f"  Extracting activations for {len(negative_texts)} negative examples..."
            )
        neg_acts = extract_activations_from_text(
            model, tokenizer, negative_texts, layer, batch_size, device, verbose=False,
            use_all_tokens=use_all_tokens, exclude_last_n_tokens=exclude_last_n_tokens
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
        activation_data: ActivationData, learning_rate: float, num_epochs: int,
        l2_reg: float = 0.0, normalize: bool = True
    ):
        """Train linear probe with contrastive loss and optional L2 regularization.

        Args:
            activation_data: Training activations
            learning_rate: Learning rate
            num_epochs: Number of epochs
            l2_reg: L2 regularization strength (lambda parameter)
            normalize: Whether to normalize activations
        """
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        pos_acts = activation_data.positive_acts.to(device).to(torch.float32)
        neg_acts = activation_data.negative_acts.to(device).to(torch.float32)

        # Normalize activations if requested (Apollo's approach)
        norm_mean = None
        norm_std = None
        if normalize:
            all_acts = torch.cat([pos_acts, neg_acts], dim=0)
            norm_mean = all_acts.mean(dim=0, keepdim=True)
            norm_std = all_acts.std(dim=0, keepdim=True)
            norm_std = torch.clamp(norm_std, min=1e-8)

            pos_acts = (pos_acts - norm_mean) / norm_std
            neg_acts = (neg_acts - norm_mean) / norm_std

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
            contrastive_loss = -pos_scores.mean() + neg_scores.mean()

            # Add L2 regularization penalty
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

            correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
            total = len(pos_scores) + len(neg_scores)
            accuracy = (correct.float() / total).item()

        metrics = {
            "final_loss": best_loss,
            "l2_reg": l2_reg,
            "normalize": normalize,
            "normalization_mean": norm_mean.cpu().squeeze() if norm_mean is not None else None,
            "normalization_std": norm_std.cpu().squeeze() if norm_std is not None else None,
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
        use_all_tokens=additional_params_dict.get('use_all_tokens', True),
        exclude_last_n_tokens=additional_params_dict.get('exclude_last_n_tokens', 0),
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
            use_all_tokens=additional_params_dict.get('use_all_tokens', True),
            exclude_last_n_tokens=additional_params_dict.get('exclude_last_n_tokens', 0),
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
            train_activation_data, learning_rate, num_epochs,
            l2_reg=additional_params_dict.get('l2_reg', 0.0),
            normalize=additional_params_dict.get('normalize', True)
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

    # Also save probe with normalization parameters (Apollo format)
    probe_data_with_norm = {
        "weights": probe_weights,
        "normalize": train_metrics.get("normalize", True),
        "normalization_mean": train_metrics.get("normalization_mean"),
        "normalization_std": train_metrics.get("normalization_std"),
    }
    probe_full_path = probe_dir / "probe.pt"
    torch.save(probe_data_with_norm, probe_full_path)

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
def upload_dataset_files(dataset_name: str, files_data: str):
    """Upload dataset files to Modal volume.

    Args:
        dataset_name: Name for the dataset
        files_data: JSON string containing dictionary of {filename: file_content}
    """
    import json
    from pathlib import Path

    print(f"Uploading dataset '{dataset_name}' to volume...")

    # Parse JSON string to dictionary
    files_dict = json.loads(files_data) if isinstance(files_data, str) else files_data

    # Create dataset directory on volume
    volume_dataset_path = Path(VOLUME_PATH) / "datasets" / dataset_name
    volume_dataset_path.mkdir(parents=True, exist_ok=True)

    # Write each file
    for filename, content in files_dict.items():
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
    layers: str = "",  # Changed from Optional[List[int]] to str for Modal CLI compatibility
    learning_rate: float = 1e-3,
    num_epochs: int = 100,
    batch_size: int = 8,
    seed: int = 42,
    additional_params: str = "",  # Changed from Optional[Dict[str, Any]] to str for Modal CLI compatibility
) -> Dict[str, Any]:
    """Sweep across layers to find best probe using AUROC.

    Args:
        dataset_name: Name of dataset (e.g., "roleplaying")
        model_name: HuggingFace model name
        method: Training method
        layers: JSON string of layer indices or empty string for all layers
        learning_rate: Learning rate for gradient-based methods
        num_epochs: Number of training epochs
        batch_size: Batch size for activation extraction
        seed: Random seed
        additional_params: JSON string of additional parameters

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

    # Parse string parameters into correct types
    if layers:
        layers_list = json.loads(layers) if isinstance(layers, str) else layers
    else:
        layers_list = None

    if additional_params:
        additional_params_dict = json.loads(additional_params) if isinstance(additional_params, str) else additional_params
    else:
        additional_params_dict = {}

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

    def extract_activations_from_text(model, tokenizer, texts, layer, batch_size=8, device="cuda",
                                     use_all_tokens=True, exclude_last_n_tokens=0):
        all_activations = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            inputs = tokenizer(batch_texts, return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
            with torch.no_grad():
                outputs = model(**inputs, output_hidden_states=True)
                hidden_states = outputs.hidden_states[layer]

                if use_all_tokens:
                    # Use mean of all response tokens (Apollo's approach)
                    attention_mask = inputs.attention_mask.unsqueeze(-1).float()

                    # Exclude last N tokens if specified (for REPE dataset)
                    if exclude_last_n_tokens > 0:
                        batch_size_local, seq_len, hidden_dim = hidden_states.shape
                        for j in range(batch_size_local):
                            # Find last valid token position
                            last_pos = attention_mask[j, :, 0].sum().long() - 1
                            # Zero out the last N tokens
                            start_exclude = max(0, last_pos - exclude_last_n_tokens + 1)
                            attention_mask[j, start_exclude:last_pos+1, :] = 0

                    # Compute masked mean
                    masked_hidden_states = hidden_states * attention_mask
                    token_counts = attention_mask.sum(dim=1).clamp(min=1)
                    mean_activations = masked_hidden_states.sum(dim=1) / token_counts
                    all_activations.append(mean_activations.cpu())
                else:
                    # Use last token only (legacy)
                    last_token_acts = hidden_states[:, -1, :]
                    all_activations.append(last_token_acts.cpu())

        return torch.cat(all_activations, dim=0)

    def extract_contrastive_activations(model, tokenizer, dataset_pairs, layer, batch_size=8, device="cuda",
                                       use_all_tokens=True, exclude_last_n_tokens=0):
        positive_texts = [pair.positive for pair in dataset_pairs]
        negative_texts = [pair.negative for pair in dataset_pairs]
        pos_acts = extract_activations_from_text(model, tokenizer, positive_texts, layer, batch_size, device,
                                                use_all_tokens, exclude_last_n_tokens)
        neg_acts = extract_activations_from_text(model, tokenizer, negative_texts, layer, batch_size, device,
                                                use_all_tokens, exclude_last_n_tokens)
        return ActivationData(positive_acts=pos_acts, negative_acts=neg_acts)

    def train_massmean(activation_data):
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
            "separation": (pos_scores.mean() - neg_scores.mean()).item(),
        }
        return direction.cpu(), metrics

    def train_linear_contrastive(activation_data, learning_rate, num_epochs, l2_reg=0.0, normalize=True):
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        pos_acts = activation_data.positive_acts.to(device).to(torch.float32)
        neg_acts = activation_data.negative_acts.to(device).to(torch.float32)

        # Normalize activations if requested (Apollo's approach)
        norm_mean = None
        norm_std = None
        if normalize:
            all_acts = torch.cat([pos_acts, neg_acts], dim=0)
            norm_mean = all_acts.mean(dim=0, keepdim=True)
            norm_std = all_acts.std(dim=0, keepdim=True)
            norm_std = torch.clamp(norm_std, min=1e-8)
            pos_acts = (pos_acts - norm_mean) / norm_std
            neg_acts = (neg_acts - norm_mean) / norm_std

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

            # Contrastive loss with L2 regularization
            contrastive_loss = -pos_scores.mean() + neg_scores.mean()
            l2_penalty = l2_reg * (direction.norm() ** 2)
            loss = contrastive_loss + l2_penalty

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
            "l2_reg": l2_reg,
            "normalize": normalize,
            "normalization_mean": norm_mean.cpu().squeeze() if norm_mean is not None else None,
            "normalization_std": norm_std.cpu().squeeze() if norm_std is not None else None,
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
    if layers_list is None:
        num_layers = model.config.num_hidden_layers
        layers_list = list(range(num_layers))

    print(f"Sweeping layers: {layers_list}")
    print()

    # Sweep layers
    results = []
    all_probes = {}

    for layer in layers_list:
        print(f"Layer {layer}:")

        # Extract activations
        print("  Extracting training activations...")
        train_acts = extract_contrastive_activations(
            model, tokenizer, train_data, layer, batch_size, "cuda",
            use_all_tokens=additional_params_dict.get('use_all_tokens', True),
            exclude_last_n_tokens=additional_params_dict.get('exclude_last_n_tokens', 0)
        )

        # Train probe
        print(f"  Training with {method}...")
        if method == "linear-contrastive":
            probe_weights, train_metrics = train_linear_contrastive(
                train_acts, learning_rate, num_epochs,
                l2_reg=additional_params_dict.get('l2_reg', 0.0),
                normalize=additional_params_dict.get('normalize', True)
            )
        elif method == "massmean":
            probe_weights, train_metrics = train_massmean(train_acts)
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

        # Convert tensors to lists for JSON serialization
        norm_mean = train_metrics.get('normalization_mean')
        norm_std = train_metrics.get('normalization_std')

        metrics = {
            'layer': layer,
            'train_accuracy': train_metrics['accuracy'],
            'train_separation': train_metrics['separation'],
            'val_accuracy': val_accuracy,
            'val_auroc': val_auroc,
            'l2_reg': train_metrics.get('l2_reg', 0.0),
            'normalize': train_metrics.get('normalize', True),
            'normalization_mean': norm_mean.tolist() if norm_mean is not None and hasattr(norm_mean, 'tolist') else None,
            'normalization_std': norm_std.tolist() if norm_std is not None and hasattr(norm_std, 'tolist') else None,
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

    # Save best probe with descriptive name including l2_reg
    l2_reg_str = f"_l2{best_result.get('l2_reg', 0.0)}".replace(".", "p")
    probe_name = f"{dataset_name}_{model_name.split('/')[-1]}_{method}_layer{best_layer}{l2_reg_str}"
    probe_dir = Path(VOLUME_PATH) / "models" / "probes" / probe_name
    probe_dir.mkdir(parents=True, exist_ok=True)

    probe_state_dict = {
        "weight": best_probe.unsqueeze(0),
        "bias": torch.zeros(1),
    }
    torch.save(probe_state_dict, probe_dir / "probe_head.bin")

    # Also save probe with normalization parameters (Apollo format)
    # Note: normalization_mean and normalization_std are already converted to lists in metrics
    # but we need to convert them back to tensors for the probe.pt file
    import numpy as np
    norm_mean_list = best_result.get("normalization_mean")
    norm_std_list = best_result.get("normalization_std")

    probe_data_with_norm = {
        "weights": best_probe,
        "normalize": best_result.get("normalize", True),
        "normalization_mean": torch.tensor(norm_mean_list) if norm_mean_list is not None else None,
        "normalization_std": torch.tensor(norm_std_list) if norm_std_list is not None else None,
    }
    probe_full_path = probe_dir / "probe.pt"
    torch.save(probe_data_with_norm, probe_full_path)

    probe_config_data = {
        "hidden_size": 4096,
        "layer_idx": best_layer,
        "probe_type": f"{method}_probe",
        "source_model": model_name,
        "source_dataset": dataset_name,
    }
    with open(probe_dir / "probe_config.json", "w") as f:
        json.dump(probe_config_data, f, indent=2)

    # Clean up metrics for JSON serialization (remove tensor objects)
    def clean_metrics(metrics):
        cleaned = {}
        for k, v in metrics.items():
            if k not in ['normalization_mean', 'normalization_std']:
                cleaned[k] = v
        return cleaned

    best_result_clean = clean_metrics(best_result)
    results_clean = [clean_metrics(m) for m in results]

    sweep_metadata = {
        "dataset": dataset_name,
        "model": model_name,
        "method": method,
        "layers_tested": layers_list,
        "best_layer": best_layer,
        "best_metrics": best_result_clean,
        "all_results": results_clean,
    }
    with open(probe_dir / "layer_sweep_results.json", "w") as f:
        json.dump(sweep_metadata, f, indent=2)

    VOLUME.commit()
    print(f"Saved best probe to: {probe_dir}")

    return {
        "best_layer": best_layer,
        "best_probe_name": probe_name,
        "best_metrics": best_result_clean,
        "all_results": results_clean,
        "volume_path": str(probe_dir),
    }


@app.function(
    gpu=GPU_CONFIG_8B,
    volumes={VOLUME_PATH: VOLUME},
    image=image,
    timeout=3600,
)
def evaluate_probe_on_modal(
    probe_name: str,
    eval_dataset_name: str,
    model_name: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
    use_all_tokens: bool = True,
    exclude_last_n_tokens: int = 5,
):
    """Evaluate a saved probe on a different dataset for OOD testing.

    Args:
        probe_name: Name of the saved probe (e.g., "repe_honesty_roleplay_Meta-Llama-3.1-8B-Instruct_linear-contrastive_layer20_l25p0")
        eval_dataset_name: Dataset to evaluate on (e.g., "repe_honesty")
        model_name: Model name (must match the probe's training model)
        use_all_tokens: Whether to use all tokens (matching probe training)
        exclude_last_n_tokens: Number of tokens to exclude from the end

    Returns:
        Dictionary with evaluation metrics including AUROC
    """
    import torch
    import json
    from pathlib import Path
    from sklearn.metrics import roc_auc_score
    import numpy as np

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 70)
    print("Cross-Dataset Probe Evaluation")
    print("=" * 70)
    print(f"Probe: {probe_name}")
    print(f"Evaluation Dataset: {eval_dataset_name}")
    print(f"Model: {model_name}")
    print("=" * 70)
    print()

    # Step 1: Load the saved probe
    print("Step 1/4: Loading saved probe...")
    probe_dir = Path(VOLUME_PATH) / "models" / "probes" / probe_name

    if not probe_dir.exists():
        raise FileNotFoundError(f"Probe not found: {probe_dir}")

    # Load probe config to get layer info
    config_path = probe_dir / "probe_config.json"
    with open(config_path, "r") as f:
        probe_config = json.load(f)
    layer = probe_config["layer_idx"]

    # Load probe weights with normalization parameters
    probe_path = probe_dir / "probe.pt"
    probe_data = torch.load(probe_path, map_location=device)
    probe_weights = probe_data["weights"].to(device)
    normalize = probe_data.get("normalize", True)
    norm_mean = probe_data.get("normalization_mean")
    norm_std = probe_data.get("normalization_std")

    if norm_mean is not None:
        norm_mean = torch.tensor(norm_mean, device=device)
    if norm_std is not None:
        norm_std = torch.tensor(norm_std, device=device)

    print(f"  ✓ Loaded probe from layer {layer}")
    print(f"  ✓ Normalization: {normalize}")
    print()

    # Step 2: Load evaluation dataset
    print("Step 2/4: Loading evaluation dataset...")
    dataset_path = Path(VOLUME_PATH) / "datasets" / eval_dataset_name

    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    # Load test/val data
    test_file = dataset_path / "test.jsonl"
    val_file = dataset_path / "val.jsonl"

    eval_data = []
    eval_file = test_file if test_file.exists() else val_file

    with open(eval_file, "r") as f:
        for line in f:
            data = json.loads(line)
            eval_data.append(
                ContrastivePair(
                    positive=data["positive"],
                    negative=data["negative"],
                    metadata=data.get("metadata"),
                )
            )

    print(f"  ✓ Loaded {len(eval_data)} evaluation examples")
    print()

    # Step 3: Load model and extract activations
    print("Step 3/4: Loading model and extracting activations...")
    model, tokenizer = load_model_and_tokenizer(model_name, device="cuda")

    # Extract activations
    eval_activations = []
    for batch_start in range(0, len(eval_data), 8):
        batch_end = min(batch_start + 8, len(eval_data))
        batch = eval_data[batch_start:batch_end]

        batch_texts = []
        for pair in batch:
            batch_texts.append(pair.positive)
            batch_texts.append(pair.negative)

        acts = extract_activations(
            model,
            tokenizer,
            batch_texts,
            layer=layer,
            use_all_tokens=use_all_tokens,
            exclude_last_n_tokens=exclude_last_n_tokens,
        ).to(device)

        eval_activations.append(acts)

    eval_acts = torch.cat(eval_activations, dim=0)
    pos_acts = eval_acts[0::2]  # Even indices are positive
    neg_acts = eval_acts[1::2]  # Odd indices are negative

    print(f"  ✓ Extracted activations for {len(eval_data)} pairs")
    print()

    # Step 4: Evaluate probe
    print("Step 4/4: Evaluating probe...")

    # Apply normalization if needed
    if normalize and norm_mean is not None and norm_std is not None:
        pos_acts = (pos_acts - norm_mean) / (norm_std + 1e-8)
        neg_acts = (neg_acts - norm_mean) / (norm_std + 1e-8)

    # Compute scores
    with torch.no_grad():
        pos_scores = pos_acts @ probe_weights
        neg_scores = neg_acts @ probe_weights

        # Compute accuracy
        correct = (pos_scores > 0).sum() + (neg_scores < 0).sum()
        total = len(pos_scores) + len(neg_scores)
        accuracy = (correct.float() / total).item()

        # Compute AUROC
        all_scores = torch.cat([pos_scores, neg_scores]).cpu().numpy()
        all_labels = np.array([1] * len(pos_scores) + [0] * len(neg_scores))
        auroc = roc_auc_score(all_labels, all_scores)

        # Additional metrics
        mean_pos_score = pos_scores.mean().item()
        mean_neg_score = neg_scores.mean().item()
        separation = mean_pos_score - mean_neg_score

    metrics = {
        "accuracy": accuracy,
        "auroc": auroc,
        "mean_pos_score": mean_pos_score,
        "mean_neg_score": mean_neg_score,
        "separation": separation,
        "num_examples": len(eval_data),
    }

    print()
    print("=" * 70)
    print("Evaluation Results:")
    print(f"  Accuracy: {accuracy:.4f}")
    print(f"  AUROC: {auroc:.4f}")
    print(f"  Mean Positive Score: {mean_pos_score:.4f}")
    print(f"  Mean Negative Score: {mean_neg_score:.4f}")
    print(f"  Separation: {separation:.4f}")
    print("=" * 70)

    return metrics


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
