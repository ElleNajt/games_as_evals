# Werewolf Integration Status

## ✅ Completed

### 1. Unified Backend System (fully tested, 48 tests passing)
- `src/backends/` - Claude, OpenRouter, Modal backends
- `src/player.py` - GamePlayer with automatic logging
- `src/probes/` - Probe registry with GPU configs

### 2. Unified Config System (26 tests passing)
- `src/config/player_config.py` - Per-player backend/model/probe configuration
- `src/config/game_config.py` - Base class with git/config hash tracking
- Automatic experiment naming: `{experiment}_{githash}_{confighash}[_dirty]`

### 3. Unified Logging System (26 tests passing)
- `src/logging/results_logger.py` - JSONL logging with directory structure
- Directory format: `results/{game_name}/{experiment_name}/game{N}/`
- Automatic config saving and message logging

### 4. Werewolf Game Files (8 tests passing)
- ✅ `src/games/werewolf/game_state.py` - Copied, no changes needed
- ✅ `src/games/werewolf/config.py` - WerewolfConfig using unified GameConfig
  - Per-role player configuration (werewolves, seer, villagers)
  - All werewolf-specific settings (probe monitoring, CoT, instructions)
  - Legacy config loader for backward compatibility
- ✅ `src/games/werewolf/__init__.py` - Module exports

### 5. GameCoordinator - Partial Refactor
- ✅ Imports updated to use unified system
- ✅ `__init__` method refactored to use:
  - WerewolfConfig instead of old GameConfig
  - ResultsLogger for directory/config management
  - Per-player GamePlayer instances with backends
  - Automatic git/config hash handling (no manual subprocess calls)

## 🚧 In Progress / TODO

### GameCoordinator Remaining Work

The game_coordinator.py file is partially refactored. **Key changes needed:**

#### 1. Replace `self.backend.call()` with `self.players[player_name].query()`
   
   **Old pattern:**
   ```python
   response, metadata = self.backend.call(prompt, system_prompt, max_retries=1)
   ```
   
   **New pattern:**
   ```python
   # GamePlayer.query() returns GenerationResult
   result = self.players[player_name].query(
       prompt=prompt,
       max_tokens=512,
       temperature=0.7
   )
   # result.text - the response
   # result.tokens - token list (Modal only)
   # result.top_k_logits - logits (Modal only)  
   # result.probe_scores - ProbeScores object (Modal with probe only)
   ```

#### 2. Update `call_agent()` method (lines ~300-420)

   Current code:
   - Uses `self.backend.call(prompt, system_prompt, max_retries=1)`
   - Returns `(response, metadata)` tuple
   
   Needs to:
   - Get player from `self.players[player_name]`
   - Call `player.query(prompt, ...)`
   - Extract metadata from `GenerationResult`:
     - `result.text` → response text
     - `result.probe_scores` → probe activations/scores
     - `result.tokens` → token list
   - Note: Logging is now automatic via ResultsLogger, but we may want additional game-specific logging

#### 3. Update `_capture_role_reveal_activations()` (lines ~187-260)

   This method captures probe activations right after role reveal. Needs to:
   - Use `player.query()` instead of `self.backend.call()`
   - Extract probe scores from `GenerationResult.probe_scores`

#### 4. Remove references to old backend types

   Lines that check `isinstance(self.backend, ModalProbeBackend)` etc:
   - Line 214: `if isinstance(self.backend, ModalProbeBackend):`
   - Line 591: `if not isinstance(self.backend, (ProbeBackend, ModalProbeBackend)):`
   
   Replace with checks like:
   - Check if `result.probe_scores is not None`
   - Or check player's backend type via `player.backend`

#### 5. Update metadata handling

   Old system returned metadata dict with:
   ```python
   {
       "activations": {
           "aggregate_score": float,
           "token_scores": List[float],
           ...
       }
   }
   ```
   
   New system uses `ProbeScores` dataclass:
   ```python
   @dataclass
   class ProbeScores:
       aggregate_score: float
       token_scores: List[float]
       phase_scores: Optional[Dict[str, float]] = None
       metadata: Dict[str, Any] = field(default_factory=dict)
   ```

#### 6. System prompt handling

   Old pattern: Pass system_prompt to `backend.call()`
   New pattern: System prompt is set when creating GamePlayer, but can be overridden via messages
   
   For now: GamePlayer uses the system_prompt from PlayerConfig. If different system prompts are needed per-call, we can:
   - Modify the prompt to include role-specific instructions
   - Or update GamePlayer to support per-call system prompt override

## File Locations

```
src/
├── backends/              # Unified backends
│   ├── base.py
│   ├── claude_backend.py
│   ├── openrouter_backend.py
│   └── modal_backend.py
├── config/                # Unified config system
│   ├── __init__.py
│   ├── game_config.py
│   └── player_config.py
├── logging/               # Unified logging system
│   ├── __init__.py
│   └── results_logger.py
├── games/
│   └── werewolf/
│       ├── __init__.py
│       ├── game_state.py        # ✅ Ready
│       ├── config.py            # ✅ Ready (WerewolfConfig)
│       └── game_coordinator.py  # 🚧 Partially refactored
├── player.py              # GamePlayer with logging
├── probes/                # Probe registry
│   ├── __init__.py
│   ├── registry.py
│   └── display.py
└── tests/
    ├── test_backends.py          # 26 tests passing
    ├── test_probes.py            # 22 tests passing
    ├── test_config.py            # 14 tests passing
    ├── test_logging.py           # 12 tests passing
    └── test_werewolf_config.py   # 8 tests passing
```

## Testing Status

**Total: 82 tests passing**
- Backend tests: 26 passing
- Probe tests: 22 passing
- Config tests: 14 passing
- Logging tests: 12 passing
- Werewolf config tests: 8 passing

## Next Steps

1. **Complete game_coordinator.py refactor** (main remaining work)
   - Update `call_agent()` to use `GamePlayer.query()`
   - Update `_capture_role_reveal_activations()`
   - Remove old backend type checks
   - Test basic game flow

2. **Create end-to-end test**
   - Test running a simple werewolf game with the new system
   - Verify logging works correctly
   - Verify probe scores are captured

3. **Documentation**
   - Add examples of running werewolf with new config
   - Document how to create custom player configurations
   - Example scripts for common scenarios

4. **Copy other games** (3SAT, TTL)
   - Follow same pattern as werewolf
   - Create game-specific configs extending GameConfig
   - Adapt game coordinators to use unified system
