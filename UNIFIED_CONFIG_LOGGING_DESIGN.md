# Unified Config and Logging Design

## Overview

Create unified systems for:
1. **Game configuration** with automatic hashing and git tracking
2. **Results directory structure** following research principles
3. **Message logging** at the player level (all prompts, responses, and metadata)

## Extracted Patterns from Werewolf

### 1. Directory Structure Pattern

```
results/
└── {experiment_name}_{git_hash}_{config_hash}_{dirty_flag}/
    ├── game0/
    │   ├── config.json           # Full config
    │   ├── game_log.txt           # High-level game events
    │   ├── llm_log.txt            # All LLM interactions
    │   ├── game_state.json        # Final game state
    │   └── activations/           # Probe data
    ├── game1/
    └── ...
```

**Key features:**
- `git_hash`: Short git hash (7 chars) from `git rev-parse --short HEAD`
- `config_hash`: SHA256 of config JSON (7 chars)
- `dirty_flag`: `_dirty` if uncommitted changes, empty otherwise
- Each game gets incrementing ID (game0, game1, ...)

### 2. Config Pattern

```python
class GameConfig:
    # Game-specific params
    # Backend params
    # Logging params
    
    def to_dict(self) -> dict:
        """Serialize to dict"""
    
    @classmethod
    def from_file(cls, path: str) -> 'GameConfig':
        """Load from JSON"""
    
    def save(self, path: str):
        """Save to JSON"""
```

### 3. Logging Pattern

Werewolf tracks:
- `game_log.txt`: High-level events (turn start, votes, eliminations)
- `llm_log.txt`: Every LLM call with full context
- `player_reasoning`: Private CoT for each player
- `player_activations`: Probe scores for each player
- `cumulative_scores`: Running totals

## Proposed Unified System

### 1. Base Config Class

```python
# src/config.py

from abc import ABC
from dataclasses import dataclass, field, asdict
import json
import hashlib
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

@dataclass
class GameConfig(ABC):
    """
    Base class for game configurations.
    
    All game configs should inherit from this and add game-specific fields.
    """
    # Backend configuration (common to all games)
    backend_type: str = "claude"  # claude, openrouter, modal
    probe: Optional[str] = None   # deception_8b, deception_70b, hallucination_8b
    
    # Logging configuration
    output_dir: str = "./results"
    
    # Automatically computed (don't set manually)
    git_hash: Optional[str] = field(default=None, init=False)
    config_hash: Optional[str] = field(default=None, init=False)
    is_dirty: bool = field(default=False, init=False)
    
    def __post_init__(self):
        """Compute git and config hashes."""
        # Get git hash
        try:
            self.git_hash = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except:
            self.git_hash = "nogit"
        
        # Check if dirty
        try:
            subprocess.check_output(
                ["git", "diff", "--quiet"],
                stderr=subprocess.DEVNULL
            )
            self.is_dirty = False
        except subprocess.CalledProcessError:
            self.is_dirty = True
        except:
            self.is_dirty = False
        
        # Compute config hash
        config_dict = self.to_dict()
        # Exclude auto-computed fields from hash
        config_dict.pop("git_hash", None)
        config_dict.pop("config_hash", None)
        config_dict.pop("is_dirty", None)
        
        config_json = json.dumps(config_dict, sort_keys=True)
        self.config_hash = hashlib.sha256(config_json.encode()).hexdigest()[:7]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameConfig':
        """Create from dictionary."""
        return cls(**data)
    
    @classmethod
    def from_file(cls, path: str) -> 'GameConfig':
        """Load from JSON file."""
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def save(self, path: str):
        """Save to JSON file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def get_experiment_name(self, experiment_base: str) -> str:
        """
        Generate experiment directory name with hashes.
        
        Format: {experiment_base}_{git_hash}_{config_hash}[_dirty]
        """
        dirty_suffix = "_dirty" if self.is_dirty else ""
        return f"{experiment_base}_{self.git_hash}_{self.config_hash}{dirty_suffix}"
```

### 2. Results Logger

```python
# src/logging.py

from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

class ResultsLogger:
    """
    Manages results directory and logging for a game run.
    
    Handles:
    - Creating results directory with proper naming
    - Saving config
    - Logging all player interactions
    - Tracking probe activations
    """
    
    def __init__(
        self,
        config: GameConfig,
        experiment_name: str,
        game_id: Optional[int] = None
    ):
        """
        Args:
            config: Game configuration
            experiment_name: Base name for experiment
            game_id: Game number (auto-assigned if None)
        """
        self.config = config
        
        # Create experiment directory
        exp_dir_name = config.get_experiment_name(experiment_name)
        self.exp_dir = Path(config.output_dir) / exp_dir_name
        self.exp_dir.mkdir(parents=True, exist_ok=True)
        
        # Get game ID
        if game_id is None:
            game_id = self._get_next_game_id()
        self.game_id = game_id
        
        # Create game directory
        self.game_dir = self.exp_dir / f"game{game_id}"
        self.game_dir.mkdir(parents=True, exist_ok=True)
        
        # Save config
        config.save(self.game_dir / "config.json")
        
        # Initialize log files
        self.game_log = self.game_dir / "game_log.txt"
        self.message_log = self.game_dir / "messages.jsonl"  # JSONL for easy parsing
        
        # Track player interactions
        self.player_messages: Dict[str, List[Dict]] = {}
        
        self.log_event(f"Game {game_id} started")
        self.log_event(f"Config hash: {config.config_hash}")
        self.log_event(f"Git hash: {config.git_hash}")
        if config.is_dirty:
            self.log_event("WARNING: Uncommitted changes present")
    
    def _get_next_game_id(self) -> int:
        """Find next available game ID in experiment directory."""
        existing = [d for d in self.exp_dir.iterdir() 
                   if d.is_dir() and d.name.startswith("game")]
        if not existing:
            return 0
        
        numbers = []
        for d in existing:
            try:
                num = int(d.name.replace("game", ""))
                numbers.append(num)
            except ValueError:
                continue
        
        return max(numbers) + 1 if numbers else 0
    
    def log_event(self, message: str):
        """Log a high-level game event."""
        timestamp = datetime.now().isoformat()
        with open(self.game_log, 'a') as f:
            f.write(f"[{timestamp}] {message}\n")
    
    def log_message(
        self,
        player_name: str,
        prompt: str,
        response: str,
        system_prompt: Optional[str] = None,
        probe_scores: Optional[Dict] = None,
        tokens: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ):
        """
        Log a complete player interaction.
        
        Saves to JSONL format for easy loading and analysis.
        """
        if player_name not in self.player_messages:
            self.player_messages[player_name] = []
        
        message_data = {
            "timestamp": datetime.now().isoformat(),
            "player": player_name,
            "system_prompt": system_prompt,
            "prompt": prompt,
            "response": response,
            "probe_scores": probe_scores,
            "tokens": tokens,
            "metadata": metadata or {}
        }
        
        self.player_messages[player_name].append(message_data)
        
        # Append to JSONL
        with open(self.message_log, 'a') as f:
            f.write(json.dumps(message_data) + '\n')
    
    def save_final_state(self, game_state: Dict[str, Any]):
        """Save final game state to JSON."""
        with open(self.game_dir / "game_state.json", 'w') as f:
            json.dump(game_state, f, indent=2)
    
    def get_player_history(self, player_name: str) -> List[Dict]:
        """Get all messages for a specific player."""
        return self.player_messages.get(player_name, [])
```

### 3. Integrated GamePlayer with Logging

```python
# src/player.py (updated)

class GamePlayer:
    def __init__(
        self,
        name: str,
        backend: LLMBackend,
        system_prompt: str = "",
        logger: Optional[ResultsLogger] = None
    ):
        self.name = name
        self.backend = backend
        self.system_prompt = system_prompt
        self.logger = logger
    
    def query(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> GenerationResult:
        """Query with automatic logging."""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        result = self.backend.generate(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # Log if logger is attached
        if self.logger:
            probe_scores = None
            if result.probe_scores:
                probe_scores = {
                    "aggregate": result.probe_scores.aggregate_score,
                    "token_scores": result.probe_scores.token_scores,
                    "phase_scores": result.probe_scores.phase_scores,
                    "metadata": result.probe_scores.metadata
                }
            
            self.logger.log_message(
                player_name=self.name,
                prompt=prompt,
                response=result.text,
                system_prompt=self.system_prompt,
                probe_scores=probe_scores,
                tokens=result.tokens,
                metadata={"max_tokens": max_tokens, "temperature": temperature}
            )
        
        return result
```

## Usage Example

```python
from games_as_evals import create_backend, GamePlayer
from games_as_evals.config import GameConfig
from games_as_evals.logging import ResultsLogger

# Define game-specific config
@dataclass
class WerewolfConfig(GameConfig):
    # Inherits backend_type, probe, output_dir, git_hash, config_hash, is_dirty
    
    # Game-specific params
    num_players: int = 12
    num_werewolves: int = 3
    max_turns: int = 5
    provide_probe_scores: bool = False

# Create config
config = WerewolfConfig(
    backend_type="modal",
    probe="deception_8b",
    num_players=12,
    num_werewolves=3
)

# Create logger (handles results directory automatically)
logger = ResultsLogger(config, experiment_name="baseline_run")
# Creates: results/baseline_run_a5038fb_3f2e8a1/game0/

# Create backend and players
backend = create_backend(config.backend_type, probe=config.probe)
alice = GamePlayer("Alice", backend, "You are a werewolf...", logger=logger)

# Play game (all interactions automatically logged)
result = alice.query("Who should we eliminate?")
# Logged to: results/.../game0/messages.jsonl

# Save final state
logger.save_final_state({
    "winner": "werewolves",
    "turns": 3,
    "eliminations": [...]
})
```

## Benefits

1. **Automatic reproducibility**: Git hash + config hash + dirty flag
2. **Centralized logging**: All player interactions in one place
3. **Easy analysis**: JSONL format for messages (one per line)
4. **No duplication**: Common logic extracted from games
5. **Research-compliant**: Follows research principles (git hash in path)
6. **Player-level logging**: Each player tracks its own interactions

## Migration Path

1. Create `src/config.py` and `src/logging.py`
2. Update `src/player.py` to accept optional logger
3. Each game creates its own config subclass
4. Games use `ResultsLogger` instead of manual directory creation
5. Remove game-specific config/logging code
