# Implementation Status: Logits Support

## Summary

**Feature:** Top-k logits support for Modal backend  
**Status:** ✅ Implementation complete, ⏳ Integration testing pending  
**Date:** 2025-11-15

## What Was Implemented

### ✅ Core Implementation (Complete)

1. **Modal Service** (`src/modal_deployments/unified_probe_service.py`)
   - Modified `_generate_with_probe_impl()` to accept `top_k_logits` parameter
   - Uses vLLM's `SamplingParams(logprobs=k)` to extract log probabilities
   - Extracts and formats logprobs as `List[Dict[str, float]]`
   - Returns logits alongside text, tokens, and probe scores

2. **Modal Backend Client** (`src/backends/modal_backend.py`)
   - Added `top_k_logits` parameter to constructor
   - Updated `supports_logits` property
   - Passes parameter through to service
   - Populates `GenerationResult.top_k_logits` field

3. **Backend Factory** (`src/backends/__init__.py`)
   - Added `top_k_logits` parameter to `create_backend()`
   - Passes through to ModalBackend

4. **Tests** (`src/tests/`)
   - Updated `test_backends.py` with logits tests
   - Created `test_logits.py` with comprehensive test suite
   - All unit tests pass (with mocks)

### ✅ Documentation (Complete)

1. **LOGITS_IMPLEMENTATION.md** - Implementation details and API reference
2. **PROBE_FORMATS.md** - Probe format specifications and upload guide
3. **TESTING_GUIDE.md** - Step-by-step testing instructions
4. **test_modal_integration.py** - Integration test suite (6 tests)

### ⏳ Integration Testing (Blocked)

**Blocked by:** No Modal authentication in current environment

**Requires:**
1. Modal CLI setup: `modal setup`
2. Probes uploaded to volume
3. Service deployed: `modal deploy src/modal_deployments/unified_probe_service.py`

**Created issues:**
- `games_as_evals-x5c`: Upload probes to Modal volume
- `games_as_evals-uhe`: Run integration tests

## What Works (Verified)

### ✅ Verified via Unit Tests

- Parameter flow through API layers
- Type signatures correct
- `supports_logits` property logic
- Backend initialization with various configurations
- Factory function parameter passing

### ✅ Verified via Code Review

- vLLM API usage correct (based on vLLM 0.6.3 docs)
- Logprobs extraction logic sound
- Token-to-string conversion implemented
- Multi-probe compatibility maintained

## What Remains Untested

### ❌ Not Yet Verified

1. **vLLM Integration**
   - Does vLLM actually return logprobs in expected format?
   - Are logprob values correct?
   - Does token alignment work properly?

2. **Probe + Logits Interaction**
   - Can probes and logits coexist?
   - Does multi-probe + logits work?
   - Are there performance issues?

3. **Edge Cases**
   - Empty responses
   - Very long responses (>2048 tokens)
   - Special tokens (EOS, BOS, etc.)
   - Temperature = 0 vs temperature > 0

4. **End-to-End Flow**
   - GamePlayer + logger + logits
   - JSONL logging of logits
   - Multi-game scenarios

## How to Test (For User)

### Quick Test (< 5 minutes)

```bash
# 1. Setup Modal
modal setup

# 2. Deploy service
modal deploy src/modal_deployments/unified_probe_service.py

# 3. Quick validation
python -c "
from src.backends import create_backend
backend = create_backend('modal', probe='deception_8b', top_k_logits=10)
result = backend.generate([{'role': 'user', 'content': 'Hello'}], max_tokens=10)
print('Logits count:', len(result.top_k_logits))
print('Tokens count:', len(result.tokens))
print('Match:', len(result.top_k_logits) == len(result.tokens))
"
```

### Full Test (10-15 minutes)

```bash
# Run comprehensive integration test
python test_modal_integration.py

# Check results
cat modal_integration_results.json
```

See `TESTING_GUIDE.md` for detailed instructions.

## Potential Issues & Mitigations

### Issue 1: vLLM logprobs format mismatch

**Risk:** Low  
**Reason:** Using official vLLM API, format is documented  
**Mitigation:** Integration test will catch this immediately

### Issue 2: Token alignment off-by-one

**Risk:** Medium  
**Reason:** EOS/BOS tokens might complicate alignment  
**Mitigation:** Code handles EOS token explicitly, integration test validates

### Issue 3: Performance degradation

**Risk:** Low  
**Reason:** vLLM computes logits anyway, minimal overhead  
**Expected:** < 5% latency increase  
**Mitigation:** Performance benchmark in TESTING_GUIDE.md

### Issue 4: Multi-probe runs generation N times

**Current:** Each probe triggers separate generation  
**Impact:** With temperature > 0, slight variation in outputs  
**Future improvement:** Single generation with multiple hooks

## API Usage Examples

### Basic Usage

```python
from backends import create_backend

# Enable logits
backend = create_backend("modal", probe="deception_8b", top_k_logits=10)

result = backend.generate(
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=50
)

# Access logits
for i, (token, logits) in enumerate(zip(result.tokens, result.top_k_logits)):
    print(f"Token {i}: {token}")
    for alt_token, logprob in list(logits.items())[:3]:
        print(f"  {alt_token}: {logprob:.3f}")
```

### With Multiple Probes

```python
backend = create_backend(
    "modal",
    probes=["deception_8b", "hallucination_8b"],
    top_k_logits=5
)

result = backend.generate(...)

# Access both probes and logits
print(result.probe_scores["deception_8b"].aggregate_score)
print(result.probe_scores["hallucination_8b"].aggregate_score)
print(result.top_k_logits[0])  # First token's top-5
```

## Commits

- `88fdc18` - Add top-k logits support to Modal backend
- `1d71085` - Add probe formats documentation and integration test
- `370bf15` - Add comprehensive testing guide and create remaining test issues

## Dependencies

- modal >= 1.2.0
- vllm == 0.6.3
- torch >= 2.0.0
- transformers >= 4.40.0

## Next Steps

1. **User authenticates Modal** (`modal setup`)
2. **User uploads probes** (see PROBE_FORMATS.md)
3. **User deploys service** (`modal deploy ...`)
4. **User runs integration tests** (`python test_modal_integration.py`)
5. **If tests pass:** Close bd issues, update README with examples
6. **If tests fail:** Debug, fix, retest

## Success Criteria

Integration tests pass when:

- ✅ All 6 test cases in `test_modal_integration.py` pass
- ✅ `len(top_k_logits) == len(tokens)` for all responses
- ✅ Logprobs are negative floats (or ~0)
- ✅ Each logit dict has ≤ k entries (where k = top_k_logits)
- ✅ Can combine probes + logits without errors
- ✅ Logits saved correctly to JSONL logs
- ✅ Performance overhead < 10%

## Confidence Level

**Implementation:** 95% confident
- Using official vLLM API
- Code structure is sound
- Unit tests pass
- Similar patterns work in other projects

**Integration:** 70% confident without testing
- Need to verify vLLM behavior
- Need to test actual probe interaction
- Edge cases need validation

**After integration tests:** Will be 95%+ confident

## Known Limitations

1. **Multi-probe inefficiency:** Runs generation N times (acceptable for now)
2. **Prompt logits not returned:** Only generation logits (by design)
3. **Top-k only:** Cannot get full vocabulary logits (would be huge)
4. **Modal only:** Claude/OpenRouter don't support logits (expected)

## Future Enhancements

- [ ] Single-pass multi-probe generation (optimization)
- [ ] Prompt token logits (if needed)
- [ ] Entropy/perplexity calculation from logits
- [ ] Logit lens support (intermediate layers)
- [ ] Full vocabulary mode (for research use)
