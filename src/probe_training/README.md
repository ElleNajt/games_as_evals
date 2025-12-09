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
src/probes/
├── __init__.py              # Module initialization
├── config.py                # TrainingConfig dataclass
├── dataset.py               # Dataset loading + checksum verification
├── methods.py               # All training methods (single file)
├── registry.py              # ProbeRegistry for managing probes
├── train.py                 # Modal training app + CLI
├── probe_metadata.json      # Git-tracked probe registry
└── README.md                # This file
```

## Usage

### Training a Probe

```bash
# Train locally (for testing)
python -m src.probes.train \
  --dataset roleplaying \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --method linear-contrastive \
  --layer 22 \
  --local

# Train on Modal (production)
python -m src.probes.train \
  --dataset roleplaying \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --method linear-contrastive \
  --layer 22 \
  --upload \
  --hf-repo your-username/probe-repo
```

### Loading a Probe

```python
from src.probes import ProbeRegistry

# Get probe path (downloads if needed, verifies integrity)
registry = ProbeRegistry()
probe_path = registry.get_probe_path("roleplaying-llama8b-linear-contrastive")

# Load probe weights
import torch
probe_weights = torch.load(probe_path)
```

### Creating a New Dataset

```python
from src.probes import Dataset
from pathlib import Path

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

Probes are named: `{dataset}-{model_abbrev}-{method}`

Examples:
- `roleplaying-llama8b-linear-contrastive`
- `truthfulqa-llama70b-massmean`

Model abbreviations:
- `llama8b`: meta-llama/Meta-Llama-3.1-8B-Instruct
- `llama70b`: meta-llama/Llama-3.3-70B-Instruct

## Training Methods

- **linear-contrastive**: Linear probe with contrastive loss
- **massmean**: Difference of means (no gradient descent)
- **lda**: Linear Discriminant Analysis
- **lat**: Linear Artificial Tomography (Apollo research)

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

## TODO

- [ ] Implement training methods (currently stubs)
- [ ] Add Modal integration for GPU training
- [ ] Implement HuggingFace upload/download
- [ ] Add activation extraction from models
- [ ] Create example datasets
- [ ] Add comprehensive tests
