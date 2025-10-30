# Unified Backend System for LLM Games

A unified backend abstraction layer for LLM-based games with optional probe integration for deception and hallucination detection.

## Overview

This package provides:
- **Unified interface** for multiple LLM backends (Claude, OpenRouter, Modal)
- **Probe integration** for deception/hallucination detection via Modal
- **Simple player abstraction** (`GamePlayer`) that works across all backends
- **Display helpers** for showing probe scores to players

## Installation

```bash
pip install -r requirements.txt
```

### Backend-Specific Setup

**Claude Backend:**
```bash
# Install Claude CLI
# See: https://github.com/anthropics/claude-cli
```

**OpenRouter Backend:**
```bash
# Set API key
export OPENROUTER_API_KEY="your-key-here"
```

**Modal Backend:**
```bash
# Login to Modal
modal setup

# Ensure probe deployments are running
# (werewolf-apollo-probe, hallucination-probe-backend, etc.)
```

## Quick Start

### Basic Usage

```python
from games_as_evals import GamePlayer, create_backend

# Create a backend
backend = create_backend("claude")  # or "openrouter", "modal"

# Create a player
alice = GamePlayer(
    name="Alice",
    backend=backend,
    system_prompt="You are Alice, a strategic 3-SAT player."
)

# Query the player
result = alice.query("What's your move?")
print(result.text)
```

### With Probe Support

```python
from games_as_evals import GamePlayer, create_backend
from games_as_evals.probes import format_probe_annotation

# Create Modal backend with deception probe
backend = create_backend("modal", probe="deception_8b")

alice = GamePlayer("Alice", backend, "You are a strategic player.")

# Generate response
result = alice.query("Will you help me win?")

# Check probe scores
if result.probe_scores:
    print(f"Deception score: {result.probe_scores.aggregate_score:.2f}")
    
    # Format for display to other players
    annotated = format_probe_annotation(
        "Alice",
        result.text,
        result.probe_scores,
        style="inline"  # "I'll help you [PROBE: HIGH]"
    )
```

## API Reference

### Backends

**`create_backend(backend_type, **kwargs)`**

Create a backend instance.

- `backend_type`: `"claude"`, `"openrouter"`, or `"modal"`
- For OpenRouter: `model="meta-llama/llama-3.1-70b-instruct"`
- For Modal: `probe="deception_8b"` or `"hallucination_8b"`

### GamePlayer

**`GamePlayer(name, backend, system_prompt="")`**

Unified player abstraction.

**`player.query(prompt, max_tokens=512, temperature=0.7)`**

Generate a response. Returns `GenerationResult`:
- `text`: Generated text (always present)
- `tokens`: Token list (Modal only, else `None`)
- `top_k_logits`: Top-k logits (Modal only, else `None`)  
- `probe_scores`: Probe scores (Modal with probe only, else `None`)

### Probe Display

**`format_probe_annotation(speaker, text, probe_scores, style)`**

Format probe scores for display:
- `style="inline"`: `"Statement [PROBE: HIGH]"` (3-SAT style)
- `style="summary"`: `"[LIE DETECTOR] Alice: 0.75"` (Werewolf style)
- `style="none"`: No annotation

**`categorize_score(score, all_scores=None)`**

Categorize score as `"LOW"`, `"MED"`, or `"HIGH"`.

## Available Probes

| Probe Name | Type | Model | Description |
|------------|------|-------|-------------|
| `deception_8b` | Deception | Llama 3.1 8B | Apollo roleplaying probe (Werewolf/3-SAT) |
| `deception_70b` | Deception | Llama 3.3 70B | Apollo roleplaying probe (Werewolf) |
| `hallucination_8b` | Hallucination | Llama 3.1 8B | Hallucination detection (Two Truths and a Lie) |

## Testing

Run tests:
```bash
# All tests
pytest src/tests/

# Specific test file
pytest src/tests/test_backends.py -v

# Skip slow integration tests
pytest -m "not slow"
```

## Architecture

### Backend Abstraction

```
LLMBackend (ABC)
├── ClaudeBackend
│   └── Returns: text only
├── OpenRouterBackend  
│   └── Returns: text only
└── ModalBackend
    └── Returns: text + tokens + probe_scores
```

### Data Flow

```
GamePlayer.query(prompt)
    ↓
backend.generate(messages)
    ↓
GenerationResult(
    text="...",
    tokens=[...],        # Modal only
    probe_scores=...     # Modal with probe only
)
```

## Example: 3-SAT Game Integration

```python
from games_as_evals import GamePlayer, create_backend
from games_as_evals.probes import format_probe_annotation, categorize_score

# Setup
backend = create_backend("modal", probe="deception_8b")
alice = GamePlayer("Alice", backend, "You are Alice, a strategic 3-SAT player...")

# Negotiation phase
conversation_history = [...]
all_probe_scores = []

prompt = f"{game_state}\n\nConversation:\n{conversation_history}\n\nYour response:"
result = alice.query(prompt, max_tokens=200)

# Display to other players (with probe annotation)
if result.probe_scores:
    all_probe_scores.append(result.probe_scores.aggregate_score)
    
    annotated = format_probe_annotation(
        "Alice",
        result.text,
        result.probe_scores,
        style="inline",
        all_scores=all_probe_scores  # For adaptive thresholds
    )
    print(annotated)  # "I'll set x3=True [PROBE: HIGH]"
else:
    print(result.text)
```

## Design Principles

1. **Single unified pattern**: All games use the same `GamePlayer` interface
2. **Null handling**: Non-Modal backends return `None` for unsupported features
3. **Game logic stays in games**: This package only handles LLM queries and probe scoring
4. **Flexible display**: Games choose how to format probe scores for their context

## Contributing

When adding new probes:

1. Deploy probe service to Modal
2. Add config to `src/probes/registry.py`:
```python
PROBE_REGISTRY["new_probe"] = ProbeConfig(
    probe_id="...",
    probe_type="deception",  # or "hallucination"
    model_name="...",
    layer=22,
    modal_app_name="...",
    description="..."
)
```

## License

MIT
