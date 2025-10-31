# TTL Game Migration Plan

## Current Status

TTL (Two Truths and a Lie) game files have been copied from the old repo but **not yet migrated** to use the unified backend system.

## Current Implementation

The TTL game currently:
- Uses Modal service directly via `get_probe_service()` function
- Calls `service.generate_with_probe.remote()` with old interface
- Has hardcoded probe parameters (`probe_id`, `repo_id`, `threshold`)
- Doesn't use the unified `GamePlayer` interface

### Files to Migrate

1. **src/games/ttl/deceiver.py** - Deceiver player that generates statements
2. **src/games/ttl/auditor.py** - Auditor player that detects lies
3. **src/games/ttl/orchestrator.py** - Game coordinator
4. **src/games/ttl/ground_truth.py** - Claude verification
5. **src/games/ttl/two_truths_and_a_lie.py** - Main game script
6. **src/games/ttl/two_truths_about_me.py** - Personal facts variant

## Migration Steps

### 1. Create TTL Config Classes

Create `src/games/ttl/config.py`:

```python
from dataclasses import dataclass
from typing import Optional
from src.config.player_config import PlayerConfig
from src.config.game_config import GameConfig


@dataclass
class TTLPlayerConfig(PlayerConfig):
    """Configuration for TTL player."""
    role: str  # "deceiver" or "auditor"


@dataclass
class TTLConfig(GameConfig):
    """Configuration for TTL game."""
    game_name: str = "ttl"
    use_real_world_facts: bool = False  # If True, deceiver generates from knowledge
    num_rounds: int = 1
    
    deceiver_config: TTLPlayerConfig
    auditor_config: TTLPlayerConfig
```

### 2. Update Deceiver to Use GamePlayer

Replace direct Modal calls with GamePlayer interface:

**Before**:
```python
def generate_real_world_facts_ttl(service, probe_id, repo_id, temperature):
    result = service.generate_with_probe.remote(
        messages=messages,
        probe_id=probe_id,
        repo_id=repo_id,
        threshold=0.3,
        max_tokens=200,
        temperature=temperature,
    )
```

**After**:
```python
def generate_real_world_facts_ttl(player: GamePlayer, config: TTLPlayerConfig):
    result = player.generate(
        messages=messages,
        max_tokens=200,
        temperature=config.temperature,
    )
    # Probe scores available in result.probe_scores if probe enabled
```

### 3. Update Auditor

Similar changes to use `GamePlayer` instead of direct service calls.

### 4. Update Orchestrator

Replace game logic to:
- Accept `TTLConfig` instead of individual parameters
- Create `GamePlayer` instances for deceiver and auditor
- Use `ResultsLogger` for output

**Current signature**:
```python
def run_game_round(
    facts: Optional[List[str]] = None,
    probe_id: str = "llama3_1_8b_lora_lambda_kl=0.5",
    repo_id: Optional[str] = None,
    temperature: float = 0.7,
    use_real_world_facts: bool = False,
) -> Dict[str, Any]:
```

**New signature**:
```python
def run_game_round(
    config: TTLConfig,
    facts: Optional[List[str]] = None,
) -> Dict[str, Any]:
```

### 5. Create Test Script

Create `test_ttl_modal.py` similar to `test_werewolf_modal.py`:

```python
from src.games.ttl.config import TTLConfig, TTLPlayerConfig
from src.games.ttl.orchestrator import run_game_round
from src.backends.backend_factory import create_backend

# Create config
deceiver_config = TTLPlayerConfig(
    backend_type="modal",
    model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
    probe_name="hallucination_8b",  # Use hallucination probe for TTL
    enable_probes=True,
    role="deceiver",
)

auditor_config = TTLPlayerConfig(
    backend_type="modal",
    model_name="meta-llama/Meta-Llama-3.1-8B-Instruct",
    probe_name="hallucination_8b",
    enable_probes=True,
    role="auditor",
)

config = TTLConfig(
    deceiver_config=deceiver_config,
    auditor_config=auditor_config,
    use_real_world_facts=True,
)

# Run game
result = run_game_round(config)
print(json.dumps(result, indent=2))
```

## Key Differences from Werewolf

1. **Simpler structure**: TTL is essentially one turn (deceiver → auditor)
2. **Different probe**: TTL should use hallucination probe, not deception probe
3. **No state**: No complex game state like werewolf (roles, deaths, votes)
4. **Ground truth**: TTL has Claude verification of truth/lie

## Probe Choice

TTL should use **hallucination_8b** probe because:
- Detecting lies about factual statements
- Hallucination probe trained to detect false statements
- Deception probe is more about intent to deceive

## Benefits After Migration

- Consistent interface with werewolf
- Easy to switch between backends (Claude, OpenRouter, Modal)
- Unified logging and results format
- Single probe service to maintain

## Estimated Effort

- **Config classes**: 30 minutes
- **Deceiver update**: 1 hour
- **Auditor update**: 30 minutes
- **Orchestrator update**: 1 hour
- **Test script**: 30 minutes
- **Testing and debugging**: 1-2 hours

**Total**: 4-5 hours

## Current Workaround

TTL can still be run using the old interface, but it won't benefit from:
- Unified logging
- Easy backend switching
- Consistent probe interface
