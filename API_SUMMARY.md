# Backend API and Service Summary

## Overview

The backend provides a unified interface for LLM generation with optional probe-based deception/hallucination detection and top-k logits extraction. All data is automatically logged to JSONL files for analysis.

## Quick Start

```python
from src.backends import create_backend
from src.player import GamePlayer
from src.result_logging.results_logger import ResultsLogger
from src.config.game_config import GameConfig

# 1. Create backend with probes and logits
backend = create_backend(
    "modal",
    probe="deception_8b",
    top_k_logits=10
)

# 2. Create player (optional: with logging)
config = GameConfig(git_hash="abc123", output_dir="results")
logger = ResultsLogger(config, "my_game", "experiment1")
player = GamePlayer("Alice", backend, logger=logger)

# 3. Generate
result = player.query("What's your strategy?")

# 4. Access all data
print(result.text)                              # Generated text
print(result.tokens)                            # Token list
print(result.probe_scores["deception_8b"])     # Probe scores
print(result.top_k_logits[0])                  # First token's alternatives
```

## Backends Available

### 1. Claude Backend
```python
backend = create_backend("claude")
```
- Uses `claude -p` CLI
- Returns: text only
- Supports: probes ❌, logits ❌
- Use case: Quick testing, human-like responses

### 2. OpenRouter Backend
```python
backend = create_backend(
    "openrouter",
    model="meta-llama/llama-3.1-70b-instruct"
)
```
- Uses OpenRouter API
- Returns: text only
- Supports: probes ❌, logits ❌
- Use case: Access to many models, no GPU needed

### 3. Modal Backend (Full-Featured)
```python
backend = create_backend(
    "modal",
    probes=["deception_8b", "hallucination_8b"],
    top_k_logits=10
)
```
- Uses Modal + vLLM deployment
- Returns: text + tokens + probes + logits
- Supports: probes ✅, logits ✅
- Use case: Research, experiments, full observability

## API Reference

### create_backend()

```python
def create_backend(
    backend_type: str,          # "claude", "openrouter", "modal"
    model: str = None,          # Model name (for Modal defaults)
    probe: str = None,          # Single probe (backward compat)
    probes: List[str] = None,   # Multiple probes
    top_k_logits: int = 0,      # Number of top logits (0=disabled)
    **kwargs
) -> LLMBackend
```

**Examples:**
```python
# Claude
create_backend("claude")

# OpenRouter
create_backend("openrouter", model="anthropic/claude-3.5-sonnet")

# Modal with defaults (both deception + hallucination for 8B)
create_backend("modal", model="meta-llama/Meta-Llama-3.1-8B-Instruct")

# Modal with specific probe
create_backend("modal", probe="deception_8b")

# Modal with multiple probes and logits
create_backend("modal", 
    probes=["deception_8b", "hallucination_8b"],
    top_k_logits=10
)
```

### GamePlayer

```python
class GamePlayer:
    def __init__(
        self,
        name: str,
        backend: LLMBackend,
        system_prompt: str = "",
        logger: ResultsLogger = None
    )
    
    def query(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> GenerationResult
```

### GenerationResult

```python
@dataclass
class GenerationResult:
    text: str                                    # Always present
    tokens: Optional[List[str]]                  # Modal only
    top_k_logits: Optional[List[Dict[str, float]]]  # Modal with top_k_logits>0
    probe_scores: Optional[ProbeScores]          # Modal with probes
```

**Example:**
```python
result = player.query("Hello")

# Text (all backends)
result.text  # "Hi there!"

# Tokens (Modal only)
result.tokens  # ["Hi", " there", "!"]

# Logits (Modal with top_k_logits>0)
result.top_k_logits  # [
                     #   {"Hi": -0.5, "Hello": -1.2, "Hey": -1.8},
                     #   {" there": -0.3, " friend": -1.5, ...},
                     #   {"!": -0.1, ".": -0.8, "?": -2.1}
                     # ]

# Probes (Modal with probes)
result.probe_scores["deception_8b"].aggregate_score  # 0.234
result.probe_scores["deception_8b"].token_scores     # [0.1, 0.2, 0.3]
```

### ProbeScores

```python
@dataclass
class ProbeScores:
    scores: Dict[str, ProbeScoreData]
    
    # Access methods
    probe_scores["deception_8b"]           # Get specific probe
    probe_scores.keys()                     # List probe names
    "deception_8b" in probe_scores          # Check if probe exists
    
    # Backward compat (single probe)
    probe_scores.aggregate_score            # First probe's aggregate
    probe_scores.token_scores               # First probe's token scores
```

```python
@dataclass
class ProbeScoreData:
    aggregate_score: float              # Mean score (0-1 after sigmoid)
    token_scores: List[float]          # Per-token scores (0-1)
    phase_scores: Optional[Dict]       # Phase-based scores (future)
    metadata: Dict[str, Any]           # Probe info (type, layer, etc.)
```

## Available Probes

| Probe Name | Type | Model | Layer | Use Case |
|------------|------|-------|-------|----------|
| `deception_8b` | Deception | Llama 3.1 8B | 12 | Werewolf, 3-SAT, roleplaying |
| `deception_70b` | Deception | Llama 3.3 70B | 22 | Werewolf (high-stakes) |
| `hallucination_8b` | Hallucination | Llama 3.1 8B | 30 | Two Truths and a Lie |

**Probe scores interpretation:**
- 0.0 = Very low deception/hallucination (truthful/factual)
- 0.5 = Neutral/uncertain
- 1.0 = Very high deception/hallucination (deceptive/false)

## Logging System

### Setup

```python
from src.result_logging.results_logger import ResultsLogger
from src.config.game_config import GameConfig

# Create config
config = GameConfig(
    git_hash="abc123",              # From git
    output_dir="results"            # Base directory
)

# Create logger
logger = ResultsLogger(
    config=config,
    game_name="werewolf",           # Game type
    experiment_base="baseline",     # Experiment name
    game_id=1                       # Optional: for multiple runs
)

# Attach to player
player = GamePlayer("Alice", backend, logger=logger)
```

### What Gets Logged

**Automatically logged for every `player.query()`:**

```jsonl
{
  "timestamp": "2025-11-15T21:15:39Z",
  "player_name": "Alice",
  "role": "assistant",
  "prompt": "What's your strategy?",
  "response": "I'll be honest and cooperative.",
  "tokens": ["I", "'ll", " be", " honest", ...],
  "top_k_logits": [
    {"I": -0.5, "My": -1.2, ...},
    {"'ll": -0.3, " will": -1.5, ...},
    ...
  ],
  "probe_scores": {
    "aggregate_score": 0.234,
    "token_scores": [0.1, 0.2, 0.3, 0.25, ...],
    "metadata": {"num_tokens": 15, "probe_type": "deception", "layer": 12}
  },
  "metadata": {
    "max_tokens": 512,
    "temperature": 0.7,
    "system_prompt": "You are Alice..."
  }
}
```

**File locations:**
```
results/
└── werewolf/
    └── abc123_2025-11-15_baseline/
        ├── config.json               # Game configuration
        ├── messages.jsonl            # All player messages
        ├── events.jsonl              # Game events (optional)
        └── results.json              # Final results (optional)
```

### Manual Logging

```python
# Log game events
logger.log_game_event("round_start", {"round": 1, "players": ["Alice", "Bob"]})
logger.log_game_event("elimination", {"player": "Bob", "reason": "voted out"})

# Save final results
logger.save_results({
    "winner": "Alice",
    "num_rounds": 5,
    "accuracy": 0.85
})
```

## Modal Service Architecture

### Deployment

```bash
# Deploy service
modal deploy src/modal_deployments/unified_probe_service.py

# Check status
modal app list | grep unified-probe-service
```

### Service Methods

The Modal service exposes these methods (called automatically by backend):

**1. Basic generation (no probes, no logits)**
```python
service.generate.remote(
    messages=[...],
    max_tokens=512,
    temperature=0.7
)
# Returns: {"generated_text": "..."}
```

**2. Single probe**
```python
service.generate_with_probe.remote(
    messages=[...],
    probe_path="deception_8b_layer12",
    max_tokens=512,
    temperature=0.7,
    top_k_logits=10
)
# Returns: {
#   "generated_text": "...",
#   "generated_tokens": [...],
#   "token_scores": [...],
#   "top_k_logits": [...]
# }
```

**3. Multiple probes**
```python
service.generate_with_probes.remote(
    messages=[...],
    probe_paths={
        "deception_8b": "deception_8b_layer12",
        "hallucination_8b": "hallucination_8b_layer30"
    },
    max_tokens=512,
    temperature=0.7,
    top_k_logits=10
)
# Returns: {
#   "generated_text": "...",
#   "generated_tokens": [...],
#   "top_k_logits": [...],
#   "probe_results": {
#     "deception_8b": {"token_scores": [...], ...},
#     "hallucination_8b": {"token_scores": [...], ...}
#   }
# }
```

### Probe Storage

Probes are stored on Modal Volume at:
```
/volume/models/probes/
├── deception_8b_layer12/
│   └── probe_detector.pt          # Apollo format
├── deception_70b_layer22/
│   └── probe_detector.pt
└── hallucination_8b_layer30/
    ├── probe_config.json           # Hallucination format
    └── probe_head.bin
```

## Data Flow

```
User Code
    ↓
GamePlayer.query(prompt)
    ↓
Backend.generate(messages)
    ↓
Modal Service.generate_with_probes.remote(...)
    ↓
vLLM (with hooks for probes + logprobs parameter)
    ↓
← Returns: text + tokens + probe_scores + top_k_logits
    ↓
ResultsLogger.log_message(...)
    ↓
results/game/experiment/messages.jsonl
```

## Performance

**Cold Start (first request):**
- Model download + load: ~60s
- Probe load: ~5s
- Total: ~65s

**Warm (subsequent requests):**
- Generation (15 tokens): ~2-3s
- With probes: ~2-3s (< 5% overhead)
- With logits: ~2-3s (< 5% overhead)
- With both: ~2-3s (< 5% overhead)

**Resource Usage:**
- Llama 3.1 8B: ~20GB GPU memory (A10G)
- Llama 3.3 70B: ~320GB GPU memory (4x H100)

## Common Patterns

### Pattern 1: Single Game with Logging

```python
# Setup
backend = create_backend("modal", probe="deception_8b", top_k_logits=10)
config = GameConfig(git_hash="abc123", output_dir="results")
logger = ResultsLogger(config, "werewolf", "baseline")

# Create players
alice = GamePlayer("Alice", backend, "You are Alice...", logger)
bob = GamePlayer("Bob", backend, "You are Bob...", logger)

# Game loop
for round in range(5):
    logger.log_game_event("round_start", {"round": round})
    
    alice_response = alice.query(f"Round {round}: What do you do?")
    bob_response = bob.query(f"Round {round}: What do you do?")
    
    # Everything auto-logged!

# Save results
logger.save_results({"winner": "Alice"})
```

### Pattern 2: Batch Analysis

```python
import json

# Read logged messages
with open("results/werewolf/exp1/messages.jsonl") as f:
    messages = [json.loads(line) for line in f]

# Analyze deception over time
for msg in messages:
    if msg["player_name"] == "Alice":
        score = msg["probe_scores"]["aggregate_score"]
        print(f"Round {msg['round']}: Deception = {score:.2f}")

# Analyze token-level patterns
for msg in messages:
    for token, logits in zip(msg["tokens"], msg["top_k_logits"]):
        # Find tokens where model was uncertain
        top_prob = max(logits.values())
        if top_prob > -0.5:  # High probability
            print(f"Uncertain token: {token}, alternatives: {logits}")
```

### Pattern 3: Multiple Probes

```python
backend = create_backend(
    "modal",
    probes=["deception_8b", "hallucination_8b"],
    top_k_logits=5
)

player = GamePlayer("Alice", backend)
result = player.query("I have been to the moon twice.")

# Check both probe types
dec_score = result.probe_scores["deception_8b"].aggregate_score
hal_score = result.probe_scores["hallucination_8b"].aggregate_score

print(f"Deception: {dec_score:.2f}")      # How deceptive?
print(f"Hallucination: {hal_score:.2f}")  # How factually incorrect?
```

## Error Handling

```python
from src.backends import create_backend

try:
    backend = create_backend("modal", probe="deception_8b", top_k_logits=10)
    result = backend.generate([{"role": "user", "content": "test"}])
    
except RuntimeError as e:
    # Modal service error
    print(f"Generation failed: {e}")
    
except KeyError as e:
    # Unknown probe
    print(f"Probe not found: {e}")
```

## Limitations

1. **Multi-probe inefficiency:** Runs generation N times (once per probe)
2. **Prompt logits not returned:** Only generation logits
3. **Top-k only:** Full vocabulary would be huge (~32k tokens)
4. **Modal GPU required:** For probes and logits
5. **Claude/OpenRouter:** No probe or logits support

## See Also

- `PROBE_FORMATS.md` - How to create and upload probes
- `TESTING_GUIDE.md` - How to test the system
- `TEST_RESULTS.md` - Integration test results
- `LOGITS_IMPLEMENTATION.md` - Implementation details
- `README.md` - Overall project documentation
