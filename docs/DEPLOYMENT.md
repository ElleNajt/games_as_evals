# Modal Deployment Guide

This guide covers deploying probe services to Modal for running games with deception/hallucination detection.

## Overview

The unified probe service runs on Modal and provides:
- **Text generation** using vLLM
- **Probe activations** (deception, hallucination detection)
- **Top-k logits** for alternative token analysis
- **Multi-probe support** (run multiple probes simultaneously)

## Current Deployment Status

### 8B Service (DEPLOYED ✓)

**App**: `unified-probe-service`  
**URL**: https://modal.com/apps/ellenajt/main/deployed/unified-probe-service

**Configuration**:
- Model: `meta-llama/Meta-Llama-3.1-8B-Instruct`
- GPU: 1x A10G (24GB)
- Volume: `unified-probe-models`
- Available probes:
  - `deception_8b` (layer 12)
  - `hallucination_8b` (layer 30)

**Status**: ✓ Deployed and tested
- Basic generation: ✓ Working
- Probe activations: ✓ Working (score: 0.812)
- Top-k logits: ✓ Working (15 positions)

### 70B Service (NOT DEPLOYED)

**Configuration needed**:
- Model: `meta-llama/Llama-3.3-70B-Instruct`
- GPU: 4x H100 (80GB each = 320GB total)
- Volume: `unified-probe-models` (same volume)
- Probes needed:
  - `deception_70b` (layer 22)
  - `hallucination_70b` (layer 30)

**Status**: ❌ Not yet deployed
- Would require separate deployment configuration
- See "70B Deployment" section below

## Quick Start: Using the Deployed 8B Service

### 1. Install Modal

```bash
pip install modal
modal setup
```

### 2. Basic Test

```python
from src.backends import create_backend

# Test basic generation
backend = create_backend('modal')
result = backend.generate(
    messages=[{'role': 'user', 'content': 'What is 2+2?'}],
    max_tokens=20
)
print(result.text)  # "2 + 2 = 4"
```

### 3. Test with Deception Probe

```python
# Test with probe
backend = create_backend('modal', probe='deception_8b', top_k_logits=10)
result = backend.generate(
    messages=[{'role': 'user', 'content': 'Tell me a convincing lie.'}],
    max_tokens=20
)

print(f"Generated: {result.text}")
print(f"Deception score: {result.probe_scores['deception_8b'].aggregate_score:.3f}")
print(f"Tokens: {result.tokens}")
print(f"Top-k logits available: {len(result.top_k_logits)} positions")
```

### 4. Run Werewolf Game with Probes

```python
from src.config.experiment_config import get_experiment_config
from src.games.werewolf import WerewolfConfig, run_werewolf_game

# Get 8B config with both probes
exp = get_experiment_config("8b_both")

# Configure game
config = WerewolfConfig(**exp.to_werewolf_config_kwargs(
    num_players=5,
    num_werewolves=2
))

# Run game
results = run_werewolf_game(config)
```

### 5. Run Expensive Integration Tests

```bash
# Run tests that require real Modal deployment
pytest -m expensive -v

# Run specific test class
pytest src/tests/test_expensive_integration.py::TestModalWithProbes8B -v
```

## Deployment Instructions

### Deploying 8B Service (Already Done)

The 8B service is already deployed. To redeploy:

```bash
modal deploy src/modal_deployments/unified_probe_service.py
```

This will:
1. Build vLLM container with A10G GPU
2. Load Llama 3.1 8B model
3. Mount `unified-probe-models` volume
4. Deploy health check endpoint

**Verify deployment**:
```bash
python -c "
from src.backends import create_backend
backend = create_backend('modal')
result = backend.generate(
    messages=[{'role': 'user', 'content': 'Hello'}],
    max_tokens=10
)
print(f'✓ Deployed: {result.text}')
"
```

### Deploying 70B Service (TODO)

To deploy the 70B service, you need to:

1. **Create separate deployment file**: `src/modal_deployments/unified_probe_service_70b.py`

2. **Modify configuration**:
```python
# In unified_probe_service_70b.py

DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
N_GPU = 4  # 4x H100
GPU_CONFIG = "H100"
GPU_MEMORY = 80  # Per GPU

app = modal.App(
    "unified-probe-service-70b",  # Different app name
    image=vllm_image
)

@app.cls(
    gpu=modal.gpu.H100(count=N_GPU),  # 4x H100
    timeout=1800,
    container_idle_timeout=600,
    volumes={VOLUME_PATH: volume},
    allow_concurrent_inputs=100
)
class UnifiedProbeService:
    # ... rest same as 8B version
```

3. **Upload 70B probes to volume**:
```bash
# You'll need to upload the probes first
# From hallucination_probes repo:
modal volume put unified-probe-models \
    deception_70b_layer22/ /deception_70b_layer22

modal volume put unified-probe-models \
    hallucination_70b_layer30/ /hallucination_70b_layer30
```

4. **Deploy**:
```bash
modal deploy src/modal_deployments/unified_probe_service_70b.py
```

5. **Update backend to use 70B app**:
```python
# In src/backends/modal_backend.py
# Add logic to select app based on model size

def create_backend(backend_type, probe=None, top_k_logits=0, model=None, **kwargs):
    if backend_type == "modal":
        # Determine app based on model
        if model and "70B" in model:
            app_name = "unified-probe-service-70b"
        else:
            app_name = "unified-probe-service"
        
        return ModalBackend(
            app_name=app_name,
            probe=probe,
            top_k_logits=top_k_logits,
            model=model,
            **kwargs
        )
```

## Volume Management

### Check what's in the volume

```bash
modal volume ls unified-probe-models
```

Expected contents:
```
/deception_8b_layer12/
    decoder.weight.pt
    encoder.weight.pt
    bias.pt
    config.json
/hallucination_8b_layer30/
    decoder.weight.pt
    encoder.weight.pt
    bias.pt
    config.json
```

### Upload new probes

```bash
# From local directory with probe files
modal volume put unified-probe-models \
    local_probe_dir/ /remote_probe_name/
```

### Remove old probes

```bash
modal volume rm unified-probe-models /old_probe_name/
```

## Available Experiment Presets

See `src/config/experiment_config.py` for preset configurations:

```python
from src.config.experiment_config import get_experiment_config

# 8B with both probes
config_8b = get_experiment_config("8b_both")

# 8B with deception only
config_8b_deception = get_experiment_config("8b_deception")

# 8B with hallucination only
config_8b_hallucination = get_experiment_config("8b_hallucination")

# 70B with both probes (requires 70B deployment)
config_70b = get_experiment_config("70b_both")
```

## Testing

### Unit Tests (No Modal Required)

```bash
# Mock-based tests
pytest src/tests/test_games_with_mocks.py -v
```

### Integration Tests (Requires Modal Deployment)

```bash
# Run expensive tests (requires deployed Modal service)
pytest -m expensive -v

# Run specific integration test
pytest src/tests/test_expensive_integration.py::TestModalWithProbes8B::test_8b_both_probes -v
```

### Manual Verification

```python
from src.backends import create_backend

# Test 1: Basic generation
backend = create_backend('modal')
result = backend.generate(
    messages=[{'role': 'user', 'content': 'Hello'}],
    max_tokens=10
)
assert result.text
print("✓ Basic generation works")

# Test 2: Probe activation
backend = create_backend('modal', probe='deception_8b')
result = backend.generate(
    messages=[{'role': 'user', 'content': 'Lie to me.'}],
    max_tokens=20
)
assert 'deception_8b' in result.probe_scores
print(f"✓ Probe score: {result.probe_scores['deception_8b'].aggregate_score:.3f}")

# Test 3: Top-k logits
backend = create_backend('modal', top_k_logits=10)
result = backend.generate(
    messages=[{'role': 'user', 'content': 'Hello'}],
    max_tokens=10
)
assert result.top_k_logits
assert len(result.top_k_logits) == len(result.tokens)
print(f"✓ Logits for {len(result.tokens)} tokens")
```

## Cost Estimation

### 8B Service (A10G)
- **GPU**: $0.60/hour (A10G)
- **Idle timeout**: 600s (10 min)
- **Cost per game**: ~$0.10 (assuming 10 min active)

### 70B Service (4x H100)
- **GPU**: $4.00/hour per H100 = $16/hour total
- **Idle timeout**: 600s (10 min)
- **Cost per game**: ~$2.67 (assuming 10 min active)

**Optimization tip**: Set `container_idle_timeout` appropriately to balance cold starts vs. idle costs.

## Troubleshooting

### Error: "No such app: unified-probe-service"

**Cause**: App not deployed  
**Solution**: 
```bash
modal deploy src/modal_deployments/unified_probe_service.py
```

### Error: "Probe not found: deception_8b"

**Cause**: Probe files not in Modal volume  
**Solution**:
```bash
# Check volume contents
modal volume ls unified-probe-models

# Upload probe if missing
modal volume put unified-probe-models \
    local_probe_dir/ /deception_8b_layer12/
```

### Error: "CUDA out of memory"

**Cause**: Model + probes too large for GPU  
**Solution**: 
- For 8B: Should work on A10G (24GB)
- For 70B: Requires 4x H100 (320GB total)

### Slow first request (cold start)

**Cause**: Modal container starting up  
**Expected**: First request ~30-60s, subsequent requests <1s  
**Solution**: Normal behavior, adjust `container_idle_timeout` to keep warm

## Next Steps

1. ✓ 8B service deployed and tested
2. ✓ Expensive integration tests created
3. TODO: Upload hallucination probes to volume
4. TODO: Create 70B deployment configuration
5. TODO: Test 70B deployment
6. TODO: Run full game experiments with probe logging

## References

- Modal docs: https://modal.com/docs
- vLLM docs: https://docs.vllm.ai/
- Probe registry: `src/probes/registry.py`
- Backend implementation: `src/backends/modal_backend.py`
- Experiment configs: `src/config/experiment_config.py`
