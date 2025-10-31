# Unified Probe Service Deployment Guide

This guide explains how to deploy and use the unified probe service that handles all probe types (deception, hallucination, etc.) via a single Modal service.

## Architecture

**Before**: Multiple Modal services (werewolf-apollo-probe, hallucination-probe-backend) with different interfaces
**After**: Single `unified-probe-service` that loads probes from volume paths and returns consistent format

### Benefits
- Single service to maintain and deploy
- Consistent interface for all probe types
- Per-token activations for flexible aggregation
- Games can compute phase scores from tokens if needed

## Deployment Steps

### 1. Prepare Probes for Upload

First, ensure you have the probe files in the correct format:

**Apollo format (deception probes)**:
```
deception_8b_layer12/
  └── probe_detector.pt      # Pickle file with directions, layers, metadata
```

**Hallucination format**:
```
hallucination_8b_layer30/
  ├── probe_config.json       # Config with layer_idx, hidden_size
  └── probe_head.bin          # PyTorch state dict
```

### 2. Upload Probes to Modal Volume

Create the volume if it doesn't exist and upload probes:

```bash
# Create volume (if needed)
modal volume create unified-probe-models

# Upload probes
modal volume put unified-probe-models probes/deception_8b_layer12 /models/probes/deception_8b_layer12
modal volume put unified-probe-models probes/deception_70b_layer22 /models/probes/deception_70b_layer22
modal volume put unified-probe-models probes/hallucination_8b_layer30 /models/probes/hallucination_8b_layer30
```

Verify uploads:
```bash
modal volume ls unified-probe-models /models/probes/
```

### 3. Deploy Unified Service

Deploy the service to Modal:

```bash
modal deploy src/modal_deployments/unified_probe_service.py
```

This creates a deployment named `unified-probe-service` with:
- **GPU**: A10G (1x) for 8B models (configurable)
- **Scaledown**: 2 minutes of idle time before shutdown
- **Timeout**: 20 minutes max per request
- **Volume**: `/models` mounted from `unified-probe-models`

### 4. Update Registry (Already Done)

The probe registry in `src/probes/registry.py` has been updated to use:
```python
ProbeConfig(
    probe_name="deception_8b",
    volume_path="deception_8b_layer12",  # Path relative to /models/probes/
    modal_app_name="unified-probe-service",
    ...
)
```

### 5. Test the Service

Test with werewolf game:
```bash
python test_werewolf_modal.py
```

Expected behavior:
- Backend connects to `unified-probe-service`
- Probes load from volume paths
- Per-token scores returned and converted to [0, 1] via sigmoid
- Game runs successfully with probe scores

## Service Interface

### Input Format

```python
service.generate_with_probe.remote(
    messages=[{"role": "user", "content": "..."}],
    probe_path="deception_8b_layer12",  # Relative to /models/probes/
    max_tokens=512,
    temperature=0.7,
)
```

### Output Format

```python
{
    "generated_text": str,              # Full generated text
    "generated_tokens": List[str],      # Token strings
    "token_scores": List[float],        # Raw probe scores (pre-sigmoid)
    "prompt_num_tokens": int,
    "generated_num_tokens": int,
}
```

**Note**: `token_scores` contains **raw logit scores** from the probe. The ModalBackend client applies sigmoid transformation to convert to [0, 1] probabilities.

## Probe Score Interpretation

After sigmoid transformation in ModalBackend:
- **0.0** = Very low deception/hallucination (truthful/factual)
- **0.5** = Neutral/uncertain
- **1.0** = Very high deception/hallucination (deceptive/false)

## Migration from Old Services

### Old System
```python
# Different services for different probe types
cls = modal.Cls.from_name("werewolf-apollo-probe", "ApolloProbeService")
cls = modal.Cls.from_name("hallucination-probe-backend", "ProbeInferenceService")

# Different return formats
# Apollo: aggregate_score, phase_scores (prompt/cot/action)
# Hallucination: probe_probs, token_entropies
```

### New System
```python
# Single service for all probes
cls = modal.Cls.from_name("unified-probe-service", "UnifiedProbeService")

# Consistent return format
# All probes: token_scores (raw), generated_text, generated_tokens
```

### Backend Changes

The ModalBackend has been simplified:
- `_ensure_connected()`: Always uses UnifiedProbeService
- `_generate_with_probe()`: Passes volume_path from config
- Response parsing: Extracts token_scores, applies sigmoid, computes aggregate

### Game-Level Changes

**No changes needed** for existing games. The ModalBackend handles the new interface transparently:
- Games still receive ProbeScores with aggregate_score and token_scores
- Phase scores set to None (games can compute from token_scores if needed)

## Troubleshooting

### Probe Not Found Error
```
ValueError: No valid probe found at /models/probes/deception_8b_layer12
```
**Fix**: Upload probe to volume (step 2 above)

### Service Connection Error
```
RuntimeError: Could not find app 'unified-probe-service'
```
**Fix**: Deploy service (step 3 above)

### Wrong Service Class Name
```
RuntimeError: Could not find class 'ApolloProbeService'
```
**Fix**: Update probe registry to use `modal_app_name="unified-probe-service"`

## Volume Management

List contents:
```bash
modal volume ls unified-probe-models /models/probes/
```

Delete probe:
```bash
modal volume rm unified-probe-models /models/probes/deception_8b_layer12
```

Download probe:
```bash
modal volume get unified-probe-models /models/probes/deception_8b_layer12 ./local_probes/
```

## Next Steps

1. Deploy unified service
2. Upload all probes to volume
3. Test with werewolf game
4. Migrate TTL game to use unified backend
5. Remove old Modal deployments (werewolf-apollo-probe, hallucination-probe-backend)
