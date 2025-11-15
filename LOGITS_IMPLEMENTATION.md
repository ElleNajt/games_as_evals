# Top-K Logits Implementation

## Summary

Added support for returning top-k logits (log probabilities) from the Modal backend, completing the backend's capability to return all requested data:

- ✅ Text responses (all backends)
- ✅ Tokens (Modal only)  
- ✅ Probe activations per token (Modal with probes)
- ✅ **Top-k logits per token (Modal with `top_k_logits>0`)** ← NEW

## Changes Made

### 1. Modal Service (`src/modal_deployments/unified_probe_service.py`)

**Modified methods:**
- `_generate_with_probe_impl()` - Added `top_k_logits` parameter
- `generate_with_probe()` - Added `top_k_logits` parameter
- `generate_with_probes()` - Added `top_k_logits` parameter

**Key implementation details:**
- Uses vLLM's `logprobs` parameter in `SamplingParams`
- Extracts logprobs from `outputs[0].outputs[0].logprobs`
- Converts token IDs to strings using tokenizer
- Returns as list of dicts: `[{"token": logprob, ...}, ...]`

### 2. Modal Backend Client (`src/backends/modal_backend.py`)

**Constructor changes:**
- Added `top_k_logits: int = 0` parameter
- Stored as instance variable `self.top_k_logits`
- Updated `supports_logits` property to return `self.top_k_logits > 0`

**Generation methods:**
- `_generate_with_probes()` - Passes `top_k_logits` to service, extracts from response
- Returns `GenerationResult` with `top_k_logits` field populated

### 3. Backend Factory (`src/backends/__init__.py`)

**Updated `create_backend()` function:**
- Added `top_k_logits: int = 0` parameter
- Passes to `ModalBackend` constructor
- Updated docstring with example

### 4. Tests

**Updated `src/tests/test_backends.py`:**
- Fixed `TestModalBackend` to match new multi-probe API
- Added tests for `top_k_logits` initialization
- Added tests for `supports_logits` property

**Created `src/tests/test_logits.py`:**
- Comprehensive logits functionality tests
- Mock-based unit tests for logits flow
- Integration tests with logging
- Edge case tests

## Usage Examples

### Basic usage with logits:

```python
from backends import create_backend

# Create backend with logits enabled
backend = create_backend(
    "modal",
    probe="deception_8b",
    top_k_logits=10  # Return top 10 tokens per position
)

# Generate
result = backend.generate(
    messages=[{"role": "user", "content": "Hello"}],
    max_tokens=50
)

# Access logits
if result.top_k_logits:
    for token_logits in result.top_k_logits:
        print(token_logits)
        # Example: {"Hello": -0.5, "Hi": -2.3, "Hey": -3.1, ...}
```

### With multiple probes:

```python
backend = create_backend(
    "modal",
    probes=["deception_8b", "hallucination_8b"],
    top_k_logits=5
)

result = backend.generate(...)

# Get probe scores AND logits
print(result.probe_scores["deception_8b"].aggregate_score)
print(result.top_k_logits[0])  # First token's top-5 logits
```

### With GamePlayer:

```python
from player import GamePlayer
from backends import create_backend

backend = create_backend("modal", probe="deception_8b", top_k_logits=10)
player = GamePlayer("Alice", backend, system_prompt="You are Alice...")

result = player.query("What's your strategy?")

# Result includes:
# - result.text: Generated text
# - result.tokens: Token list
# - result.probe_scores: Deception scores per token
# - result.top_k_logits: Top-10 logits per token
```

## Logging Integration

The `ResultsLogger` automatically logs top-k logits when present:

```python
from result_logging.results_logger import ResultsLogger
from config.game_config import GameConfig

config = GameConfig(git_hash="abc123", output_dir="results")
logger = ResultsLogger(config, "werewolf", "experiment1")

backend = create_backend("modal", probe="deception_8b", top_k_logits=10)
player = GamePlayer("Alice", backend, logger=logger)

result = player.query("Hello")

# Logged to results/werewolf/{experiment_name}/messages.jsonl:
# {
#   "timestamp": "...",
#   "player_name": "Alice",
#   "prompt": "Hello",
#   "response": "Hi there!",
#   "tokens": ["Hi", " there", "!"],
#   "top_k_logits": [{"Hi": -0.1, "Hello": -1.2, ...}, ...],
#   "probe_scores": {...}
# }
```

## Data Format

### Logits Format

Returned as `List[Dict[str, float]]` where:
- Each list element corresponds to one generated token
- Each dict maps token strings to their log probabilities
- Log probabilities are negative (higher = more likely)

Example:
```python
[
    {"Hello": -0.5, "Hi": -2.3, "Hey": -3.1},  # Token 1
    {" world": -0.3, " there": -1.8, " friend": -2.5},  # Token 2
    {"!": -0.1, ".": -0.8, "?": -2.1}  # Token 3
]
```

### Converting to Probabilities

```python
import math

def logprob_to_prob(logprob: float) -> float:
    return math.exp(logprob)

# Usage
for token_logits in result.top_k_logits:
    probs = {token: logprob_to_prob(lp) for token, lp in token_logits.items()}
    print(probs)
    # {"Hello": 0.606, "Hi": 0.100, "Hey": 0.045}
```

## Performance Notes

- Enabling logits adds minimal overhead (vLLM natively computes them)
- Higher `top_k_logits` values increase response size but not computation
- Recommended values: 5-20 for most use cases
- Set to 0 to disable (default)

## Testing

Run tests:
```bash
# All backend tests
pytest src/tests/test_backends.py -v

# Logits-specific tests  
pytest src/tests/test_logits.py -v

# Quick validation (no pytest required)
python -c "from src.backends import create_backend; b = create_backend('modal', probe='deception_8b', top_k_logits=10); print('✓ Logits enabled:', b.supports_logits)"
```

## Implementation Notes

### Why vLLM's `logprobs` instead of direct logits?

- vLLM doesn't easily expose raw logits from the model
- The `logprobs` parameter in `SamplingParams` is the official way to get this data
- Returns log probabilities (log-softmax of logits), which is what we want
- Already sorted by probability, making top-k efficient

### Alignment with tokens

- Logits list length matches `generated_tokens` length
- One-to-one correspondence: `logits[i]` describes `tokens[i]`
- Special tokens (EOS) handled correctly

### Multi-probe considerations

- Currently runs generation N times (once per probe)
- All runs use same `top_k_logits` setting
- First probe's logits are returned (with temperature>0, slight variation possible)
- Future optimization: single generation with multiple hooks (harder to implement)

## Future Enhancements

Potential improvements (not implemented):

1. **Return full vocabulary logits** - Set `logprobs=None` to get all tokens (large!)
2. **Prompt logits** - Currently only returns logits for generated tokens
3. **Logit lens** - Intermediate layer logits (requires model changes)
4. **Entropy calculation** - Compute token-level entropy from logits
5. **Perplexity** - Calculate sequence perplexity from logprobs

## Related Files

- `src/backends/base.py` - `GenerationResult` dataclass
- `src/backends/modal_backend.py` - Client implementation
- `src/modal_deployments/unified_probe_service.py` - Server implementation
- `src/result_logging/results_logger.py` - Logging integration
- `src/tests/test_logits.py` - Test suite
