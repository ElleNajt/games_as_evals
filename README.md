# LLM Games with Deception Detection

A research framework for running LLM-based games with integrated deception and hallucination detection probes. Provides a unified backend abstraction supporting multiple LLM providers (Claude, OpenRouter, Modal) with optional probe scoring and logit extraction.

## Overview

This framework enables:
- **Unified LLM interface** across Claude, OpenRouter, and Modal backends
- **Probe integration** for real-time deception and hallucination detection
- **Top-k logits extraction** for analyzing model uncertainty
- **Automatic logging** of all interactions with full metadata (tokens, probes, logits, timestamps)
- **Game implementations** for studying strategic deception

### Implemented Games

1. **Werewolf** - Social deduction game where players must identify hidden werewolves
   - Roles: Villagers, Werewolves, Seer
   - Phases: Night (werewolf selection), Day (discussion and voting)
   - Probe usage: Detect deceptive statements during discussions
   - Located in: `src/games/werewolf/`

2. **Two Truths and a Lie (TTL)** - Deceiver generates mixed true/false statements, auditor identifies the lie
   - Roles: Deceiver, Auditor
   - Modes: Real-world facts or given fact set
   - Probe usage: Hallucination detection on generated statements
   - Located in: `src/games/ttl/`

## Installation

```bash
pip install -r requirements.txt
```

### Backend-Specific Setup

**Claude Backend:**
```bash
# Install Claude CLI (https://github.com/anthropics/claude-cli)
# Then use directly - no additional setup needed
```

**OpenRouter Backend:**
```bash
export OPENROUTER_API_KEY="your-key-here"
```

**Modal Backend (for probes + logits):**
```bash
# Login to Modal
modal setup

# Deploy the unified probe service (8B)
modal deploy src/modal_deployments/unified_probe_service.py::app_8b

# (Optional) Deploy 70B service if you need 70B probes
modal deploy src/modal_deployments/unified_probe_service.py::app_70b

# (Recommended) Cache the 70B model to avoid repeated downloads
# This downloads ~140GB once and stores it on the Modal volume
# Saves 10-15 minutes on every subsequent deployment
modal run src/modal_deployments/unified_probe_service.py::download_model_to_volume_70b
```

**70B Model Caching:**

The 70B model is large (~140GB) and takes 10-15 minutes to download on each cold start. To optimize this:

1. **One-time caching** (recommended):
   ```bash
   modal run src/modal_deployments/unified_probe_service.py::download_model_to_volume_70b
   ```
   This downloads the model once to `/volume/models/huggingface/` on the Modal volume.

2. **Automatic detection**: The 70B service automatically checks for the cached model on startup:
   - If cached model exists → loads from volume (fast startup)
   - If not cached → downloads from HuggingFace (slower, but saves to cache for next time)

3. **No configuration needed**: The caching is transparent - just deploy and run. The first run without cache downloads the model, all subsequent runs use the cached version.

### Setting Up Probes

The 8B probes (`deception_8b` and `hallucination_8b`) are already uploaded to Modal. For 70B probes, you need to download and upload them first:

```bash
# Download 70B probes from HuggingFace and external repos
python probes/setup_70b_probes.py

# Upload to Modal volume
python probes/setup_70b_probes.py --upload-to-modal
```

This script:
- Downloads the hallucination 70B probe from HuggingFace (`obalcells/hallucination-probes`)
- Copies the deception 70B probe from `external_repos/deception-detection`
- Uploads both to the Modal volume at `/probes/deception_70b_layer22` and `/probes/hallucination_70b_layer30`

**Note:** You only need to run this once per Modal account. The probes are stored persistently in the Modal volume.

## Running Experiments

The easiest way to run experiments with probes is using the provided example scripts:

### Werewolf with 8B Model + Both Probes

```bash
python examples/run_werewolf_8b.py
```

This runs a 5-player Werewolf game with:
- Model: Llama 3.1 8B Instruct
- Probes: `deception_8b` + `hallucination_8b`
- Top-k logits: 10 alternatives per token
- Results saved to: `results/werewolf/werewolf_8b_demo/`

### Two Truths and a Lie with 8B Model + Both Probes

```bash
python examples/run_ttl_8b.py
```

This runs a TTL round with:
- Model: Llama 3.1 8B Instruct
- Probes: `deception_8b` + `hallucination_8b`
- Deceiver generates own facts
- Results saved to: `results/ttl/ttl_8b_demo/round1/`

### Available Experiment Configurations

You can use predefined experiment configs for consistent settings:

```python
from src.config.experiment_config import get_experiment_config

# 8B with both probes
config = get_experiment_config("8b_both")

# 8B with deception only
config = get_experiment_config("8b_deception")

# 8B with hallucination only
config = get_experiment_config("8b_hallucination")

# 70B with both probes (requires 70B deployment)
config = get_experiment_config("70b_both")
```

See `src/config/experiment_config.py` for all available presets and `examples/` for usage examples.

## Quick Start

### Basic Usage

```python
from src.backends import create_backend
from src.player import GamePlayer

# Create a backend
backend = create_backend("claude")  # or "openrouter", "modal"

# Create a player
alice = GamePlayer(
    name="Alice",
    backend=backend,
    system_prompt="You are Alice, a strategic player."
)

# Generate response
result = alice.query("What's your strategy?")
print(result.text)
```

### With Probes and Logits (Modal only)

```python
from src.backends import create_backend
from src.player import GamePlayer

# Create Modal backend with deception probe and logits
backend = create_backend(
    "modal",
    probe="deception_8b",
    top_k_logits=10
)

alice = GamePlayer("Alice", backend, "You are a strategic player.")

# Generate response with probe scoring
result = alice.query("I'm definitely telling the truth.")

# Access all data
print(f"Response: {result.text}")
print(f"Tokens: {result.tokens}")
print(f"Deception score: {result.probe_scores['deception_8b'].aggregate_score:.3f}")
print(f"Top alternatives for first token: {result.top_k_logits[0]}")
```

### With Automatic Logging

```python
from src.backends import create_backend
from src.player import GamePlayer
from src.result_logging import ResultsLogger
from src.config import GameConfig

# Setup logging
config = GameConfig(output_dir="results/my_experiment")
logger = ResultsLogger(config, game_name="werewolf", experiment_base="test")

# Create player with logger
backend = create_backend("modal", probe="deception_8b", top_k_logits=10)
alice = GamePlayer("Alice", backend, logger=logger)

# All queries are automatically logged to messages.jsonl
result = alice.query("What's your move?")

# Logs include: timestamp, player, prompt, response, tokens, probe_scores, top_k_logits
```

## Backend Comparison

| Feature | Claude | OpenRouter | Modal |
|---------|--------|------------|-------|
| **Returns text** | ✅ | ✅ | ✅ |
| **Returns tokens** | ❌ | ❌ | ✅ |
| **Probe scores** | ❌ | ❌ | ✅ |
| **Top-k logits** | ❌ | ❌ | ✅ |
| **Auto logging** | ✅ | ✅ | ✅ |
| **Use case** | Quick testing | Many models | Research |
| **Cost** | API cost | API cost | GPU time |

## Available Probes

All probes return scores in the range `[0, 1]` after sigmoid transformation:
- **0.0** = Very low deception/hallucination (truthful/factual)
- **0.5** = Neutral/uncertain
- **1.0** = Very high deception/hallucination

| Probe Name | Type | Model | Layer | Description |
|------------|------|-------|-------|-------------|
| `deception_8b` | Deception | Llama 3.1 8B | 12 | Apollo roleplaying probe |
| `deception_70b` | Deception | Llama 3.3 70B | 22 | Apollo roleplaying probe |
| `hallucination_8b` | Hallucination | Llama 3.1 8B | 12 | Factual accuracy detection |

### Multi-Probe Support

```python
# Use multiple probes simultaneously
backend = create_backend(
    "modal",
    probes=["deception_8b", "hallucination_8b"],
    top_k_logits=10
)

result = backend.generate(
    messages=[{"role": "user", "content": "Tell me something."}]
)

# Access individual probe scores
print(result.probe_scores["deception_8b"].aggregate_score)
print(result.probe_scores["hallucination_8b"].aggregate_score)
```

## Game Examples

### Running Werewolf

```python
from src.games.werewolf import WerewolfConfig, GameCoordinator

# Configure game
config = WerewolfConfig(
    num_players=5,
    num_werewolves=2,
    backend_type="modal",
    probe="deception_8b",
    top_k_logits=10,
    show_probe_scores=True  # Display probe annotations to players
)

# Run game
coordinator = GameCoordinator(config, experiment_name="test_game")
results = coordinator.run_game()

# Results logged to: results/werewolf/{experiment_name}/
print(f"Winner: {results['winner']}")
print(f"Final state: {results['final_state']}")
```

### Running Two Truths and a Lie

```python
from src.games.ttl import TTLConfig
from src.games.ttl.orchestrator_unified import run_game_round

# Configure game
config = TTLConfig(
    deceiver_backend="modal",
    auditor_backend="modal",
    deceiver_probe="deception_8b",
    auditor_probe="hallucination_8b",
    top_k_logits=10
)

# Run round
results = run_game_round(
    config=config,
    facts=["The sky is blue", "Water freezes at 0°C", "Earth orbits the sun"],
    experiment_name="ttl_test",
    round_id=1
)

# Results logged to: results/ttl/ttl_test/round1/
print(f"Auditor guessed correctly: {results['auditor_correct']}")
print(f"Deceiver statements: {results['statements']}")
```

## Logging System

All player interactions are automatically logged to JSONL files with full metadata.

### Log Structure

```
results/
└── {game_name}/
    └── {experiment_name}/
        ├── config.json          # Complete game configuration
        ├── messages.jsonl       # All player messages
        ├── events.jsonl         # Game events
        ├── results.json         # Final results
        └── visualizations/      # HTML probe visualizations (auto-generated)
            └── consolidated_probe_visualization.html
```

### Message Log Format

Each line in `messages.jsonl` contains:

```json
{
  "timestamp": "2025-11-15T21:15:39Z",
  "player_name": "Alice",
  "role": "assistant",
  "prompt": "What's your strategy?",
  "response": "I think we should vote for Bob.",
  "tokens": ["I", " think", " we", ...],
  "top_k_logits": [
    {"I": -0.5, "My": -1.2, "We": -2.1},
    ...
  ],
  "probe_scores": {
    "deception_8b": {
      "aggregate_score": 0.734,
      "token_scores": [0.1, 0.8, 0.9, ...],
      "metadata": {
        "num_tokens": 15,
        "probe_type": "deception",
        "layer": 12
      }
    }
  },
  "metadata": {
    "max_tokens": 512,
    "temperature": 0.7,
    "system_prompt": "You are Alice..."
  }
}
```

## Architecture

### Backend Abstraction

```
LLMBackend (ABC)
├── ClaudeBackend          → Returns: text
├── OpenRouterBackend      → Returns: text
└── ModalBackend           → Returns: text + tokens + probes + logits
```

### Data Flow

```
GamePlayer.query(prompt)
    ↓
backend.generate(messages, max_tokens, temperature)
    ↓
[Modal: vLLM inference + probe scoring + logit extraction]
    ↓
GenerationResult(
    text="...",
    tokens=["I", " think", ...],           # Modal only
    top_k_logits=[{...}, {...}],           # Modal only (if enabled)
    probe_scores={"deception_8b": ...}     # Modal only (if probe specified)
)
    ↓
ResultsLogger.log_message(...)  # Automatic logging to JSONL
```

## API Reference

See [API_SUMMARY.md](API_SUMMARY.md) for complete API documentation including:
- Detailed `create_backend()` parameters
- `GamePlayer` interface
- `GenerationResult` structure
- Probe configuration
- Modal service architecture
- Performance metrics

## Testing

```bash
# Run all tests
pytest src/tests/

# Specific test file
pytest src/tests/test_backends.py -v

# Test logits functionality
pytest src/tests/test_logits.py -v

# Skip slow integration tests
pytest -m "not slow"
```

## Adding New Probes

1. Train probe and export weights (`.pt` for Apollo format or `.bin` + `.json` for Hallucination format)

2. Upload to Modal volume:
```bash
modal volume put probes-volume local_probe.pt /probes/my_probe.pt
```

3. Register in `src/backends/modal_backend.py`:
```python
PROBE_PATHS = {
    "my_probe": "/probes/my_probe.pt",
    # ... existing probes
}
```

4. Use in games:
```python
backend = create_backend("modal", probe="my_probe")
```

## Project Structure

```
src/
├── backends/              # Backend implementations
│   ├── base.py           # Abstract base class
│   ├── claude.py         # Claude CLI backend
│   ├── openrouter.py     # OpenRouter API backend
│   └── modal_backend.py  # Modal + probes + logits backend
├── games/                # Game implementations
│   ├── werewolf/         # Werewolf game
│   └── ttl/              # Two Truths and a Lie
├── modal_deployments/    # Modal service deployments
│   └── unified_probe_service.py  # vLLM + probe scoring service
├── config/               # Configuration classes
├── player.py             # GamePlayer abstraction
├── result_logging/       # Logging infrastructure
└── tests/                # Test suite
```

## Design Principles

1. **Unified interface** - All backends use the same `LLMBackend` abstract class
2. **Null handling** - Non-Modal backends return `None` for unsupported features (probes, logits)
3. **Automatic logging** - All interactions logged by default with full metadata
4. **Game-agnostic** - Backend system works for any game, not just Werewolf/TTL
5. **Reproducibility** - Config and git hashes tracked for all experiments

## Training Custom Probes

Want to train your own probes for new behaviors or models? See the comprehensive guide:

**[docs/PROBE_TRAINING.md](docs/PROBE_TRAINING.md)**

This guide covers:
- Training deception probes using the `external_repos/deception-detection/` codebase
- Training hallucination probes using the `external_repos/hallucination_probes/` codebase
- Choosing the right layer for your probe
- Creating training datasets with contrasting conditions
- Exporting and integrating custom probes into this repository
- Troubleshooting common issues

Pre-trained probes are available for Llama-3.3-8B and Llama-3.3-70B models.

## Contributing

When adding new games:

1. Create directory in `src/games/{game_name}/`
2. Implement game coordinator using `GamePlayer` interface
3. Add configuration class inheriting from `GameConfig`
4. Use `ResultsLogger` for automatic logging
5. Add tests in `src/tests/`

## License

MIT
