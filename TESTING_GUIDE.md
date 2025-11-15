# Testing Guide: Modal Backend with Real Probes

## Prerequisites

Before running integration tests, you need:

1. **Modal CLI configured**
   ```bash
   pip install modal
   modal setup  # Follow prompts to authenticate
   ```

2. **Probes uploaded to Modal volume**
   - See `PROBE_FORMATS.md` for probe format details
   - Upload probes to volume `unified-probe-models`
   - Path structure: `/volume/models/probes/{probe_name}/`

3. **Modal service deployed**
   ```bash
   modal deploy src/modal_deployments/unified_probe_service.py
   ```

## Quick Validation Tests

### Test 1: Check Modal Connection

```bash
python -c "
import modal
print('Modal version:', modal.__version__)

# Try to connect to service
try:
    cls = modal.Cls.from_name('unified-probe-service', 'UnifiedProbeService')
    print('✓ Connected to unified-probe-service')
except Exception as e:
    print('✗ Cannot connect:', e)
"
```

### Test 2: Basic Generation (No Probes)

```bash
python -c "
import sys
sys.path.insert(0, 'src')

from backends import create_backend

backend = create_backend('modal')
result = backend.generate(
    messages=[{'role': 'user', 'content': 'What is 2+2?'}],
    max_tokens=20
)

print('Generated:', result.text)
print('✓ Basic generation works')
"
```

### Test 3: Single Probe

```bash
python -c "
import sys
sys.path.insert(0, 'src')

from backends import create_backend

backend = create_backend('modal', probe='deception_8b')
result = backend.generate(
    messages=[{'role': 'user', 'content': 'Tell me a lie.'}],
    max_tokens=30
)

print('Generated:', result.text)
print('Tokens:', len(result.tokens))
print('Probe score:', result.probe_scores['deception_8b'].aggregate_score)
print('✓ Probe works')
"
```

### Test 4: Logits Support

```bash
python -c "
import sys
sys.path.insert(0, 'src')

from backends import create_backend

backend = create_backend('modal', probe='deception_8b', top_k_logits=10)
result = backend.generate(
    messages=[{'role': 'user', 'content': 'Hello!'}],
    max_tokens=20
)

print('Generated:', result.text)
print('Tokens:', len(result.tokens))
print('Logits:', len(result.top_k_logits))
print('Logits match tokens:', len(result.top_k_logits) == len(result.tokens))

# Show example
if result.top_k_logits:
    print('\\nFirst token logits:')
    for token, logprob in list(result.top_k_logits[0].items())[:3]:
        print(f'  {token!r}: {logprob:.3f}')

print('✓ Logits work')
"
```

## Full Integration Test

Run the comprehensive test suite:

```bash
python test_modal_integration.py
```

This will run 6 tests covering:
1. Basic generation (no probes, no logits)
2. Single probe (deception_8b)
3. Single probe + logits
4. Multiple probes + logits
5. Logits without probes
6. Edge cases

Expected output:
```
=================================================================================
 MODAL BACKEND INTEGRATION TEST SUITE
=================================================================================

======================================================================
TEST 1: Basic generation (no probes, no logits)
======================================================================
✓ Generated text: Four.
✓ No probes: True
✓ No logits: True
PASS

... [5 more tests] ...

=================================================================================
 ALL TESTS PASSED! ✓
=================================================================================
```

## Troubleshooting

### Issue: "Cannot find app 'unified-probe-service'"

**Solution:**
```bash
# Deploy the service
modal deploy src/modal_deployments/unified_probe_service.py

# Verify deployment
modal app list | grep unified-probe-service
```

### Issue: "No valid probe found"

**Solution:**
```bash
# Check volume contents
modal volume ls unified-probe-models /models/probes/

# Upload probe if missing (see PROBE_FORMATS.md)
modal volume put unified-probe-models \
    ./local_probe/probe_detector.pt \
    /models/probes/deception_8b_layer12/probe_detector.pt
```

### Issue: "KeyError: 'deception_8b'"

**Problem:** Probe not in registry

**Solution:** Update `src/probes/registry.py` with your probe configuration

### Issue: Import errors

**Solution:**
```bash
# Make sure you're in the project directory
cd /workspace

# Run with python -m to ensure proper imports
python -m test_modal_integration
```

## Testing on RunPod

If you're using RunPod for GPU access:

1. **Push code to RunPod:**
   ```bash
   runpod push
   ```

2. **Deploy Modal service from RunPod:**
   ```bash
   runpod run "modal deploy src/modal_deployments/unified_probe_service.py"
   ```

3. **Run tests from RunPod:**
   ```bash
   runpod run "python test_modal_integration.py"
   ```

## What to Check in Test Results

When tests pass, verify:

1. **Logits structure:**
   - Each token has a dict of {token: logprob}
   - Number of logits matches number of tokens
   - Logprobs are negative (or close to 0)
   - Top-k limit is respected

2. **Probe scores:**
   - Scores are between 0 and 1 (after sigmoid)
   - Token scores list matches tokens list
   - Aggregate score is mean of token scores

3. **Integration:**
   - Can combine probes + logits
   - Can use multiple probes simultaneously
   - Logging captures all data

## Example Result Format

Check `modal_integration_results.json` after running tests:

```json
{
  "text": "The sky is blue, not green.",
  "tokens": ["The", " sky", " is", " blue", ",", " not", " green", "."],
  "top_k_logits": [
    {"The": -0.123, "A": -2.456, "This": -3.789},
    {" sky": -0.234, " sun": -1.567, " moon": -2.890},
    ...
  ],
  "probe_scores": {
    "deception_8b": {
      "aggregate_score": 0.234,
      "token_scores": [0.1, 0.2, 0.3, 0.25, 0.15, 0.4, 0.5, 0.2],
      "metadata": {"num_tokens": 8, "probe_type": "deception", "layer": 12}
    }
  }
}
```

## Performance Benchmarking

To check performance impact of logits:

```python
import time
from backends import create_backend

# Without logits
backend_no_logits = create_backend('modal', probe='deception_8b')
start = time.time()
result1 = backend_no_logits.generate([{'role': 'user', 'content': 'test'}], max_tokens=50)
time_no_logits = time.time() - start

# With logits
backend_with_logits = create_backend('modal', probe='deception_8b', top_k_logits=10)
start = time.time()
result2 = backend_with_logits.generate([{'role': 'user', 'content': 'test'}], max_tokens=50)
time_with_logits = time.time() - start

print(f"Without logits: {time_no_logits:.2f}s")
print(f"With logits: {time_with_logits:.2f}s")
print(f"Overhead: {time_with_logits - time_no_logits:.2f}s ({(time_with_logits/time_no_logits - 1)*100:.1f}%)")
```

Expected: < 5% overhead (logits are computed anyway by vLLM)

## Next Steps After Testing

Once integration tests pass:

1. ✅ Commit any fixes needed
2. ✅ Update documentation with actual performance numbers
3. ✅ Add real-world examples to README
4. ✅ Create example notebooks for common use cases
5. ✅ Set up CI/CD for automated testing

## Getting Help

If tests fail:

1. Check Modal service logs: `modal app logs unified-probe-service`
2. Review error messages in test output
3. Verify probe format matches expected structure
4. Check that model and probe hidden dimensions match
5. See PROBE_FORMATS.md troubleshooting section
