# Project Status

## Completed Work

### Unified Probe System Design ✅
- **Goal**: Single Modal service for all probe types with consistent interface
- **Implementation**:
  - Created `UnifiedProbeService` in `src/modal_deployments/unified_probe_service.py`
  - Supports both Apollo (.pt) and hallucination (.bin) probe formats
  - Returns per-token activations for flexible aggregation
  - Single interface: `generate_with_probe(messages, probe_path, ...)`

### Backend Simplification ✅
- **ModalBackend Updates**:
  - Simplified `_ensure_connected()` to use UnifiedProbeService
  - Simplified `_generate_with_probe()` to pass volume_path
  - Simplified response parsing to handle only unified format
  - Added sigmoid transformation for all probe scores
  - Removed handling of multiple legacy formats

### Configuration Updates ✅
- **ProbeConfig Changes**:
  - Changed from `probe_id`/`repo_id` to `volume_path`
  - All probes now use `modal_app_name="unified-probe-service"`
  - Registry updated with new volume paths

### Documentation ✅
- Created `UNIFIED_PROBE_DEPLOYMENT.md` with deployment guide
- Updated `README.md` with probe score format section
- Added `test_sigmoid.py` to demonstrate transformation
- Documented architecture and migration path

### TTL Game Files ✅
- Copied TTL game from old repo
- Files: orchestrator, deceiver, auditor, ground_truth, variants
- Ready for migration to unified backend

### Testing ✅
- Werewolf game test still passes with current system
- Confirmed backward compatibility with old services

## Pending Work

### 1. Deploy Unified Service (Manual Step Required)

**Probe Upload**:
```bash
# Create volume
modal volume create unified-probe-models

# Upload probes (you need to provide the actual probe files)
modal volume put unified-probe-models /path/to/deception_8b_layer12 /models/probes/deception_8b_layer12
modal volume put unified-probe-models /path/to/hallucination_8b_layer30 /models/probes/hallucination_8b_layer30
```

**Service Deployment**:
```bash
modal deploy src/modal_deployments/unified_probe_service.py
```

**Verification**:
```bash
python test_werewolf_modal.py
# Should connect to unified-probe-service instead of werewolf-apollo-probe
```

### 2. Migrate TTL Game

**Current State**: TTL uses old Modal service directly
```python
# src/games/ttl/two_truths_and_a_lie.py
cls = modal.Cls.from_name("hallucination-probe-backend", "ProbeInferenceService")
```

**Migration Steps**:
1. Update TTL to use `GamePlayer` interface (like werewolf)
2. Create `TTLConfig` similar to `WerewolfConfig`
3. Update orchestrator to use unified backend
4. Add TTL tests

### 3. Clean Up Old Deployments

After unified service is tested and working:
```bash
# Remove old services from Modal
modal app stop werewolf-apollo-probe
modal app stop hallucination-probe-backend
```

### 4. Update MODAL_DEPLOYMENT_GUIDE.md

Current guide has old service examples. Should be updated to:
- Document unified service only
- Remove references to ApolloProbeService and ProbeInferenceService
- Add volume setup instructions
- Update deployment examples

## Architecture Summary

### Current System (Working)
```
GameCoordinator
  └── GamePlayer (ModalBackend)
        └── Modal Service (werewolf-apollo-probe)
              └── ApolloProbeService
```

### Target System (Designed, Not Yet Deployed)
```
GameCoordinator
  └── GamePlayer (ModalBackend)
        └── Modal Service (unified-probe-service)
              └── UnifiedProbeService
                    └── Volume (probes/)
```

## Key Benefits of New System

1. **Single Service**: One deployment instead of multiple
2. **Consistent Interface**: Same API for all probe types
3. **Flexible Aggregation**: Games control how to aggregate token scores
4. **Simpler Backend**: Removed complex format handling
5. **Better Testing**: Single service to test and monitor

## Git History

Recent commits:
- `7ae3d7a` Copy TTL game files from old repo
- `93e7324` Add unified probe service for Modal deployments
- `9fef9e9` Simplify ModalBackend to use unified probe response format
- `5939d98` Fix remaining backend_type references in save_game_stats

## Next Session TODO

1. **Deploy to Modal** (requires probe files):
   - Upload probes to volume
   - Deploy unified service
   - Test with werewolf

2. **Migrate TTL**:
   - Create TTL config classes
   - Update to use GamePlayer
   - Add tests

3. **Documentation**:
   - Update MODAL_DEPLOYMENT_GUIDE.md
   - Add TTL game documentation

4. **Cleanup**:
   - Remove old Modal services
   - Remove old probe deployment scripts
