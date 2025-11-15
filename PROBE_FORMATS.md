# Probe Formats and Loading Guide

## Overview

The unified probe service supports two probe formats:
1. **Apollo format** - Used for deception probes from Apollo Research
2. **Hallucination format** - Used for custom hallucination detection probes

## Probe Storage Structure

Probes are stored on Modal Volume at `/volume/models/probes/`:

```
/volume/models/probes/
├── deception_8b_layer12/
│   └── probe_detector.pt          # Apollo format
├── deception_70b_layer22/
│   └── probe_detector.pt          # Apollo format
└── hallucination_8b_layer30/
    ├── probe_config.json           # Hallucination format
    └── probe_head.bin              # Hallucination format
```

## Format 1: Apollo Format (Deception Probes)

**File:** `probe_detector.pt` (pickle file)

**Required structure:**
```python
{
    "layers": int or List[int],           # Layer index (e.g., 12)
    "directions": {                        # Dict mapping layer to direction vector
        layer_idx: torch.Tensor,           # Shape: (hidden_dim,) or (1, hidden_dim)
        # or just a single tensor if not dict
    }
}
```

**Creating an Apollo probe:**
```python
import torch
import pickle

# Example: Create a deception probe for layer 12
probe_data = {
    "layers": 12,
    "directions": {
        12: torch.randn(4096)  # For Llama 3.1 8B (hidden_dim=4096)
    }
}

# Or simplified format:
probe_data = {
    "layers": [12],
    "directions": torch.randn(4096)
}

# Save
with open("probe_detector.pt", "wb") as f:
    pickle.dump(probe_data, f)
```

**What the loader does:**
1. Loads pickle file
2. Extracts layer index from `"layers"` key
3. Extracts direction vector from `"directions"` key
4. Creates `nn.Linear(hidden_dim, 1, bias=False)` layer
5. Sets weight to direction vector
6. Converts to bfloat16 and moves to GPU

## Format 2: Hallucination Format

**Files:**
- `probe_config.json` - Probe metadata
- `probe_head.bin` - PyTorch state_dict

**probe_config.json structure:**
```json
{
    "hidden_size": 4096,
    "layer_idx": 30,
    "probe_type": "hallucination",
    "description": "Hallucination detection probe for layer 30"
}
```

**probe_head.bin:**
- PyTorch state_dict from `nn.Linear(hidden_size, 1)`
- Must contain keys: `"weight"` and optionally `"bias"`

**Creating a hallucination probe:**
```python
import torch
import torch.nn as nn
import json

# 1. Create config
config = {
    "hidden_size": 4096,  # Llama 3.1 8B hidden size
    "layer_idx": 30,
    "probe_type": "hallucination",
    "description": "Example hallucination probe"
}

with open("probe_config.json", "w") as f:
    json.dump(config, f, indent=2)

# 2. Create probe head
probe_head = nn.Linear(4096, 1, bias=False)

# Initialize with your trained weights
# probe_head.weight.data = your_trained_weights

# Save state dict
torch.save(probe_head.state_dict(), "probe_head.bin")
```

## Uploading Probes to Modal Volume

### Step 1: Create Modal Volume (one-time)

```bash
modal volume create unified-probe-models
```

### Step 2: Upload Probes

**Option A: Using Modal CLI**
```bash
# Upload Apollo format probe
modal volume put unified-probe-models \
    ./local_probes/deception_8b_layer12/probe_detector.pt \
    /models/probes/deception_8b_layer12/probe_detector.pt

# Upload hallucination format probe
modal volume put unified-probe-models \
    ./local_probes/hallucination_8b_layer30/probe_config.json \
    /models/probes/hallucination_8b_layer30/probe_config.json

modal volume put unified-probe-models \
    ./local_probes/hallucination_8b_layer30/probe_head.bin \
    /models/probes/hallucination_8b_layer30/probe_head.bin
```

**Option B: Using Python script**
```python
import modal

volume = modal.Volume.from_name("unified-probe-models")

# Upload directory
with volume.batch_upload() as batch:
    batch.put_directory(
        "./local_probes/deception_8b_layer12",
        "/models/probes/deception_8b_layer12"
    )
```

### Step 3: Verify Upload

```bash
# List volume contents
modal volume ls unified-probe-models /models/probes/
```

Or use the health check:
```python
import modal

app = modal.App.lookup("unified-probe-service")
health = app.health_check.remote()
print(health)
# Should show: {"status": "healthy", "probes": {...}}
```

## Model Hidden Dimensions

Different models have different hidden dimensions. Make sure your probe matches:

| Model | Hidden Dimension |
|-------|-----------------|
| Llama 3.1 8B Instruct | 4096 |
| Llama 3.3 70B Instruct | 8192 |

## Probe Registry Configuration

After uploading probes, update `src/probes/registry.py`:

```python
PROBE_REGISTRY = {
    "my_new_probe": ProbeConfig(
        probe_name="my_new_probe",
        volume_path="my_probe_layer20",  # Matches /volume/models/probes/my_probe_layer20/
        probe_type="deception",  # or "hallucination"
        model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
        layer=20,
        description="My custom probe",
        modal_app_name="unified-probe-service",
        gpu_type="A10G",
        gpu_count=1,
        estimated_memory_gb=20
    ),
}
```

## Testing Probes

### Test 1: Health Check

```python
import modal

# Connect to service
cls = modal.Cls.from_name("unified-probe-service", "UnifiedProbeService")
service = cls()

# Check what probes are available
# (This requires a health_check function in the service)
```

### Test 2: Simple Generation

```python
from src.backends import create_backend

# Test probe loading and generation
backend = create_backend("modal", probe="deception_8b", top_k_logits=10)

result = backend.generate(
    messages=[{"role": "user", "content": "Tell me a lie."}],
    max_tokens=50,
    temperature=0.7
)

print("Text:", result.text)
print("Tokens:", len(result.tokens))
print("Probe scores:", result.probe_scores["deception_8b"].aggregate_score)
print("Logits:", len(result.top_k_logits))
```

### Test 3: Multiple Probes

```python
backend = create_backend(
    "modal",
    probes=["deception_8b", "hallucination_8b"],
    top_k_logits=5
)

result = backend.generate(
    messages=[{"role": "user", "content": "What is 2+2?"}],
    max_tokens=30
)

print("Deception:", result.probe_scores["deception_8b"].aggregate_score)
print("Hallucination:", result.probe_scores["hallucination_8b"].aggregate_score)
print("Logits per token:", len(result.top_k_logits))
```

## Common Issues

### Issue: "No valid probe found"

**Error:**
```
ValueError: No valid probe found at /volume/models/probes/my_probe. 
Expected probe_detector.pt or probe_head.bin+probe_config.json
```

**Solutions:**
1. Check volume path: `modal volume ls unified-probe-models /models/probes/`
2. Verify file names match exactly (case-sensitive)
3. Check probe_config.json is valid JSON
4. Ensure probe_head.bin is a valid torch state_dict

### Issue: "Shape mismatch"

**Error:**
```
RuntimeError: size mismatch, expected [1, 4096], got [1, 8192]
```

**Solution:** 
- Your probe was trained on a different model size
- Create new probe for correct model, or
- Change `model_name` in backend initialization

### Issue: "Module not found: modal"

**Solution:**
```bash
pip install modal
modal setup  # First time only
```

## Creating Probes from Scratch

If you need to create probes from your own training:

### For Deception Probes (Apollo format):

```python
import torch
import pickle
from sklearn.linear_model import LogisticRegression
import numpy as np

# 1. Collect activations during training
# activations: np.ndarray of shape (n_samples, hidden_dim)
# labels: np.ndarray of shape (n_samples,) - binary 0/1

# 2. Train probe
clf = LogisticRegression()
clf.fit(activations, labels)

# 3. Extract direction
direction = torch.from_numpy(clf.coef_[0])  # Shape: (hidden_dim,)

# 4. Save in Apollo format
probe_data = {
    "layers": 12,  # Your layer
    "directions": {12: direction}
}

with open("probe_detector.pt", "wb") as f:
    pickle.dump(probe_data, f)
```

### For Hallucination Probes:

```python
import torch
import torch.nn as nn
import json

# 1. Train your probe (e.g., logistic regression)
# ... training code ...

# 2. Create nn.Linear and load weights
hidden_size = 4096
probe_head = nn.Linear(hidden_size, 1, bias=False)
probe_head.weight.data = torch.from_numpy(clf.coef_).float()

# 3. Save config
config = {
    "hidden_size": hidden_size,
    "layer_idx": 30,
    "probe_type": "hallucination"
}

with open("probe_config.json", "w") as f:
    json.dump(config, f)

# 4. Save weights
torch.save(probe_head.state_dict(), "probe_head.bin")
```

## Next Steps

1. **Upload your probes** to Modal volume
2. **Update registry** in `src/probes/registry.py`
3. **Deploy service**: `modal deploy src/modal_deployments/unified_probe_service.py`
4. **Test integration** with real probes
5. **Validate logits** are returned correctly
