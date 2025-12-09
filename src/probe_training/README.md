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
  --method ccs \
  --layer 22 \
  --local

# Train on Modal (production)
python -m src.probe_training.train \
  --dataset roleplaying \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --method ccs \
  --layer 22 \
  --upload \
  --hf-repo your-username/probe-repo
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

- **ccs**: Contrast-Consistent Search (Burns et al.) - unsupervised method
- **mean_difference**: Difference of means between positive and negative activations
- **massmean**: Mass-mean direction (default method, fast and effective)

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
- [ ] Migrate additional datasets (sycophancy, persona, sandbagging)
- [ ] Add comprehensive unit tests
- [ ] Train probe suite across multiple models/layers
- [ ] Add probe evaluation metrics
