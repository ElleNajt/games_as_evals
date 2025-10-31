# Project Status

## ✅ COMPLETED: Unified Probe Service Deployment

**The unified probe service is now fully deployed and working!**

### Unified Probe System ✅
- **Goal**: Single Modal service for all probe types with consistent interface
- **Status**: ✅ **DEPLOYED AND TESTED**
- **Implementation**:
  - Created `UnifiedProbeService` in `src/modal_deployments/unified_probe_service.py`
  - Supports both Apollo (.pt) and hallucination (.bin) probe formats
  - Returns per-token activations for flexible aggregation
  - Single interface: `generate_with_probe(messages, probe_path, ...)`
  - Deployed at: https://modal.com/apps/ellenajt/main/deployed/unified-probe-service

### Probes Uploaded to Modal Volume ✅
- Created `unified-probe-models` volume on Modal
- Uploaded probes:
  - `deception_8b_layer12` (hallucination format: probe_head.bin + config.json)
  - `hallucination_8b_layer30` (hallucination format: probe_head.bin + config.json)
- Volume mounted at `/volume`, probes accessible at `/volume/models/probes/`

### Backend Simplification ✅
- **ModalBackend Updates**:
  - Simplified `_ensure_connected()` to use UnifiedProbeService
  - Simplified `_generate_with_probe()` to pass volume_path
  - Simplified response parsing to handle only unified format
  - Added sigmoid transformation for all probe scores
  - Removed handling of multiple legacy formats
  - Fixed dtype conversion (probes → bfloat16 to match vLLM)

### Configuration Updates ✅
- **ProbeConfig Changes**:
  - Changed from `probe_id`/`repo_id` to `volume_path`
  - All probes now use `modal_app_name="unified-probe-service"`
  - Registry updated with new volume paths

### Testing ✅
- **Werewolf game test PASSED with unified service**
- Test results:
  - Game completed successfully
  - Probe scores generated (0.58-0.72 range)
  - Both werewolves correctly identified and eliminated
  - Village wins!
- Backend now connects to `unified-probe-service` instead of `werewolf-apollo-probe`

### Documentation ✅
- Created `UNIFIED_PROBE_DEPLOYMENT.md` with deployment guide
- Created `TTL_MIGRATION.md` with TTL migration plan
- Updated `README.md` with probe score format section
- Added `test_sigmoid.py` to demonstrate transformation
- Documented architecture and migration path

### TTL Game Files ✅
- Copied TTL game from old repo
- Files: orchestrator, deceiver, auditor, ground_truth, variants
- Migration plan documented in `TTL_MIGRATION.md`

## Deployment Details

### Issues Resolved

1. **Import errors**: Moved torch/transformers imports inside functions (lazy loading)
2. **Modal class initialization**: Removed `__init__` conflicting with `modal.parameter()`
3. **Volume path mapping**: Fixed `/volume` mount point, files at `/volume/models/probes/`
4. **Dtype mismatch**: Convert probe weights to bfloat16 to match vLLM model
5. **Missing imports**: Added torch import in `_load_probe_if_needed` method

### Final Working Configuration

```python
# Volume setup
VOLUME = modal.Volume.from_name("unified-probe-models", create_if_missing=False)
VOLUME_PATH = "/volume"  # Mount at /volume
PROBES_DIR = Path(VOLUME_PATH) / "models" / "probes"

# Probe loading
probe_head = probe_head.to(device='cuda', dtype=torch.bfloat16)  # Match vLLM dtype

# Path resolution
path = Path("/volume/models/probes") / probe_path
```

## Current System Architecture

```
GameCoordinator
  └── GamePlayer (ModalBackend)
        └── Modal Service (unified-probe-service) ✅
              └── UnifiedProbeService ✅
                    └── Volume (probes/) ✅
                          ├── deception_8b_layer12/
                          │   ├── probe_config.json
                          │   └── probe_head.bin
                          └── hallucination_8b_layer30/
                              ├── probe_config.json
                              └── probe_head.bin
```

## Remaining Work

### 1. Migrate TTL Game (Optional)

**Current State**: TTL uses old Modal service directly
- See `TTL_MIGRATION.md` for detailed migration plan
- Estimated effort: 4-5 hours
- TTL can still run with old interface (works but not unified)

**Migration Steps**:
1. Create `TTLConfig` and `TTLPlayerConfig` classes
2. Update deceiver.py to use `GamePlayer` interface
3. Update auditor.py to use `GamePlayer` interface
4. Update orchestrator.py to accept `TTLConfig`
5. Create test script `test_ttl_modal.py`
6. Test with unified backend

### 2. Clean Up Old Deployments (Recommended)

After confirming unified service works for all use cases:
```bash
# Remove old services from Modal
modal app stop werewolf-apollo-probe
modal app stop hallucination-probe-backend
```

### 3. Update MODAL_DEPLOYMENT_GUIDE.md (Optional)

Current guide has old service examples. Could be updated to:
- Document unified service only
- Remove references to old service classes
- Add volume setup instructions
- Update deployment examples

## Key Benefits Achieved

1. ✅ **Single Service**: One deployment instead of multiple
2. ✅ **Consistent Interface**: Same API for all probe types
3. ✅ **Flexible Aggregation**: Games control how to aggregate token scores
4. ✅ **Simpler Backend**: Removed complex format handling
5. ✅ **Better Testing**: Single service to test and monitor
6. ✅ **Proven Working**: Werewolf game passing with probe scores

## Quick Start

### Running Werewolf with Unified Service

```bash
python test_werewolf_modal.py
```

### Adding New Probes

```bash
# 1. Prepare probe directory (either format)
#    Apollo: probe_detector.pt
#    Hallucination: probe_head.bin + probe_config.json

# 2. Upload to volume
modal volume put unified-probe-models /path/to/probe /models/probes/probe_name

# 3. Add to registry (src/probes/registry.py)
PROBE_REGISTRY["probe_name"] = ProbeConfig(
    probe_name="probe_name",
    volume_path="probe_name",  # Relative to /models/probes/
    probe_type="deception",  # or "hallucination"
    model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
    layer=12,
    modal_app_name="unified-probe-service",
)

# 4. Use in game config
config.probe_name = "probe_name"
```

## Git History

Recent commits:
- `70451ae` Add missing torch import in probe loading method (FINAL FIX - WORKING!)
- `7deb21b` Fix probe dtype mismatch: convert probes to bfloat16
- `f2b0c22` Fix unified probe service volume paths
- `def083a` Fix unified probe service: improve debugging and volume handling
- `93e7324` Add unified probe service for Modal deployments
- `9fef9e9` Simplify ModalBackend to use unified probe response format

## Success Metrics

- ✅ Service deployed successfully
- ✅ Probes uploaded and accessible
- ✅ Werewolf game test passing
- ✅ Probe scores in expected range (0.58-0.72)
- ✅ Game mechanics working correctly
- ✅ Both probe formats supported
- ✅ Documentation complete

## Next Steps (Optional)

1. **Migrate TTL**: Follow `TTL_MIGRATION.md` plan (4-5 hours)
2. **Add more probes**: Upload 70B model probes if needed
3. **Clean up**: Remove old Modal deployments
4. **Production use**: Start running actual experiments
