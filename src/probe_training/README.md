# Probe Training Infrastructure

This directory contains infrastructure for training activation probes for deception and hallucination detection.

## Overview

Activation probes are trained on contrastive pair datasets (truthful vs. deceptive statements) and can be used to detect deception in game-playing agents.

Key features:
- **Task-agnostic**: Probes trained on general datasets work across different games
- **Multiple training methods**: Linear-contrastive, mass-mean, LDA, LAT
- **Integrity verification**: Checksums ensure dataset/probe integrity
- **HuggingFace integration**: Store and share trained probes
- **Modal training**: Distributed GPU training on Modal

## Directory Structure

```
src/probe_training/
├── __init__.py              # Module initialization
├── config.py                # TrainingConfig dataclass
├── dataset.py               # Dataset loading + checksum verification
├── activations.py           # Activation extraction from transformer layers
├── methods.py               # All training methods (CCS, Mean Difference, Mass Mean)
├── registry.py              # ProbeRegistry for managing probes
├── train.py                 # Training CLI + Modal integration
├── migrate_dataset.py       # Dataset migration utilities
├── probe_metadata.json      # Git-tracked probe registry
└── README.md                # This file
```

## Usage

### Training a Probe

```bash
# Train locally (for testing)
python -m src.probe_training.train \
  --dataset roleplaying \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --method linear-contrastive \
  --layer 22 \
  --local

# Train with L2 regularization (Apollo's approach)
python -m src.probe_training.train \
  --dataset roleplaying \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --method linear-contrastive \
  --layer 22 \
  --additional-params l2_reg=0.001 \
  --local

# Train with last token only (legacy approach)
python -m src.probe_training.train \
  --dataset roleplaying \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --method linear-contrastive \
  --layer 22 \
  --use-all-tokens False \
  --local

# Train with REPE/instructed pairs approach (exclude last 5 tokens)
python -m src.probe_training.train \
  --dataset repe_honesty \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --method lat \
  --layer 22 \
  --exclude-last-n-tokens 5 \
  --local

# Train on Modal (production)
python -m src.probe_training.train \
  --dataset roleplaying \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --method linear-contrastive \
  --layer 22 \
  --additional-params l2_reg=0.001 \
  --upload \
  --hf-repo your-username/probe-repo
```

#### L2 Regularization for Linear-Contrastive Method

The `linear-contrastive` method now supports L2 regularization to prevent overfitting:

```python
from src.probe_training import TrainingConfig

config = TrainingConfig(
    dataset_name="roleplaying",
    model="meta-llama/Meta-Llama-3.1-8B-Instruct",
    method="linear-contrastive",
    layer=22,
    additional_params={'l2_reg': 0.001}  # L2 regularization strength
)

# Common L2 values to try:
# - 0.0: No regularization (default)
# - 0.0001: Very light regularization
# - 0.001: Light regularization (Apollo's typical value)
# - 0.01: Moderate regularization
# - 0.1: Strong regularization
```

### Loading a Probe

```python
from src.probe_training import ProbeRegistry

# Get probe path (downloads if needed, verifies integrity)
registry = ProbeRegistry()
probe_path = registry.get_probe_path("roleplaying_Meta-Llama-3.1-8B-Instruct_ccs_layer22")

# Load probe weights
import torch
probe_weights = torch.load(probe_path)
```

### Creating a New Dataset

```python
from src.probe_training import Dataset
from pathlib import Path
import json

# Create dataset directory
dataset_path = Path("datasets/my_dataset")
dataset_path.mkdir(exist_ok=True)

# Create train.jsonl and val.jsonl with contrastive pairs
# Format: {"positive": "truthful statement", "negative": "deceptive statement"}

# Generate checksums
checksums = Dataset.generate_checksums(dataset_path)
with open(dataset_path / "checksums.json", 'w') as f:
    json.dump(checksums, f, indent=2)
```

## Probe Naming Convention

Probes are named: `{dataset}_{model}_{method}_layer{layer}`

Examples:
- `roleplaying_Meta-Llama-3.1-8B-Instruct_ccs_layer22`
- `roleplaying_Meta-Llama-3.1-8B-Instruct_massmean_layer12`

The full model name is used in the probe name for clarity and to avoid ambiguity.

## Training Methods

- **linear-contrastive**: Gradient-based optimization with contrastive loss (supports L2 regularization)
- **massmean**: Mass-mean direction / Mean-Mean Subtraction (fast and effective)
- **lda**: Linear Discriminant Analysis (Fisher's Linear Discriminant)
- **lat**: Linear Artificial Tomography from RepE paper (Apollo Research)

All methods support **activation normalization** (zero mean, unit variance) following Apollo's approach.

## Activation Extraction

By default, probes use **Apollo's approach** of extracting the mean activation across ALL response tokens (not just the last token). This provides a more robust signal by aggregating information from the entire response.

You can control this behavior with the `use_all_tokens` parameter:
- `use_all_tokens=True` (default): Mean of all token activations
- `use_all_tokens=False`: Only last token activation (legacy approach)

**Important**: Different datasets use different extraction approaches. See [DATASET_DIFFERENCES.md](DATASET_DIFFERENCES.md) for critical details about:
- Instructed Pairs (REPE): Excludes last 5 tokens during training
- Roleplaying: Uses all tokens
- Evaluation: Always uses all tokens regardless of training approach

## Activation Normalization

Following Apollo Research's approach, activations are normalized to zero mean and unit variance by default:

1. **During Training**: Compute mean and std across all training activations
2. **Normalization**: `normalized = (activations - mean) / std`
3. **Saved Parameters**: Mean and std are saved with the probe
4. **Inference Time**: Same normalization is applied using saved parameters

Control normalization with `additional_params`:
```python
# Enable normalization (default)
config = TrainingConfig(..., additional_params={'normalize': True})

# Disable normalization
config = TrainingConfig(..., additional_params={'normalize': False})
```

## Inference with Trained Probes

Use the `ProbeInference` class to apply trained probes with automatic normalization:

```python
from src.probe_training.inference import ProbeInference

# Load probe (handles normalization automatically)
probe = ProbeInference("probes/deception_8b_layer12/probe.pt")

# Apply to single activation
activation = torch.randn(1, 4096)  # [batch, hidden_dim]
score = probe.apply(activation)  # Returns sigmoid(score)
logit = probe.apply(activation, return_logits=True)  # Returns raw score

# Apply to sequence with aggregation
sequence = torch.randn(2, 100, 4096)  # [batch, seq_len, hidden_dim]
attention_mask = torch.ones(2, 100)
scores = probe.apply_to_sequence(
    sequence,
    attention_mask=attention_mask,
    aggregation="mean"  # or "max", "last"
)
```

## Integrity Verification

All datasets and probes use SHA256 checksums for corruption detection:

- **Datasets**: `checksums.json` in dataset directory
- **Probes**: Checksum stored in `probe_metadata.json`

Loading fails if checksums don't match, preventing use of corrupted data.

## Git Workflow

- **Datasets**: Committed to git in `datasets/` folder
- **Probe metadata**: `probe_metadata.json` tracked in git
- **Probe weights**: Stored on HuggingFace, cached in `probes/` (gitignored)
- **Versioning**: Use git tags for probe versions (e.g., `probe/roleplaying-llama8b-linear-contrastive-v1`)

## Status

**Completed:**
- ✅ Training methods (CCS, Mean Difference, Mass Mean)
- ✅ Modal integration for distributed GPU training
- ✅ HuggingFace Hub upload/download
- ✅ Activation extraction from transformer layers
- ✅ Probe registry with auto-registration
- ✅ Dataset migration from external repos
- ✅ Example dataset (roleplaying, 371 examples)
- ✅ CLI tools (manage_probes.py)

**TODO:**
- [ ] Migrate additional datasets (strategic deception, truthfulqa, insider trading, etc.)
- [ ] Add comprehensive unit tests
- [ ] Train probe suite
- [ ] Add probe evaluation metrics
