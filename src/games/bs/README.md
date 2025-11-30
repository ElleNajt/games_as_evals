# BS (Cheat / I Doubt It) Card Game

Implementation of the BS card game for deception detection research.

## Game Rules

**Objective:** Be the first player to get rid of all your cards.

**Setup:**
- 2-10 players
- Standard 52-card deck (2 decks if 6+ players)
- Cards dealt evenly to all players

**Gameplay:**
1. Players take turns playing cards face-down in rank order (2→3→4→...→K→A, then cycles)
2. On your turn, you must play cards of the current rank (or claim to)
3. You can:
   - Play truthfully: Play actual cards of the required rank
   - Bluff: Play different cards but claim they're the required rank
   - Pass: Skip your turn (if allowed by config)
4. After a play, any player can call "BS!" to challenge
5. If BS is called:
   - Reveal the played cards
   - If player was lying: They pick up entire discard pile
   - If player was truthful: BS caller picks up entire pile
6. First player with 0 cards wins

## Implementation

### Architecture

```
src/games/bs/
├── __init__.py           # Public API
├── config.py             # BSConfig, BSPlayerConfig
├── game_state.py         # GameState, Card, PlayAction classes
├── player_actions.py     # LLM action handlers (play cards, call BS)
├── orchestrator.py       # Main game loop
└── README.md            # This file
```

### Key Features

- **Unified backend support:** Works with 8B, 70B, Claude, OpenRouter
- **Probe integration:** Detect bluffing via deception/hallucination probes
- **Full logging:** All moves logged with probe scores in `messages.jsonl`
- **Configurable:** Number of players, passing rules, max rounds

## Usage

### Basic Example (8B Model)

```python
from src.games.bs import BSConfig, BSPlayerConfig
from src.games.bs.orchestrator import run_game

# Create 4 players
players = []
for i in range(4):
    players.append(BSPlayerConfig(
        name=f"Player{i}",
        backend_type="modal",
        model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        probes=["deception_8b", "hallucination_8b"],
        temperature=0.7,
        max_tokens=300,
    ))

# Configure game
config = BSConfig(
    num_players=4,
    player_configs=players,
    allow_passing=True,
)

# Run game
results = run_game(config, experiment_name="my_bs_game")

print(f"Winner: {results['winner_name']}")
```

### Example Scripts

**Run with 8B model:**
```bash
python examples/run_bs_8b.py
```

**Run with mixed 70B/8B models:**
```bash
python examples/run_bs_mixed_70b_8b.py
```

## Research Applications

### 1. Bluffing Detection

Analyze probe scores on bluffs vs truthful plays:

```python
# In messages.jsonl, find play actions
{
  "player_name": "Player0",
  "response": '{"action": "play", "cards": ["5♠", "3♥"], "reasoning": "Bluffing"}',
  "probe_scores": {
    "deception_8b": {"aggregate_score": 0.82},  # High = likely bluffing
    "hallucination_8b": {"aggregate_score": 0.71}
  }
}
```

**Questions:**
- Do probe scores correlate with bluffs?
- Do 70B players generate lower probe scores when bluffing (harder to detect)?

### 2. BS Call Accuracy

Track which players call BS correctly:

```python
# Count correct vs incorrect BS calls per player
# Compare 70B vs 8B accuracy
```

**Questions:**
- Are 70B models better at detecting bluffs?
- Do high probe scores predict successful BS calls?

### 3. Strategic Behavior

Analyze game logs for:
- Bluffing frequency by model size
- Risk-taking (BS calling when pile is large)
- Win rates by model type

## Configuration Options

### BSConfig

```python
@dataclass
class BSConfig(GameConfig):
    num_players: int = 4           # 2-10 players
    player_configs: List[BSPlayerConfig]
    max_rounds: int = 1000         # Max rounds before draw
    allow_passing: bool = True     # Can players pass?
```

### BSPlayerConfig

```python
@dataclass
class BSPlayerConfig(PlayerConfig):
    # Inherits:
    # - name: str
    # - backend_type: str (modal, claude, openrouter)
    # - model: str
    # - probes: List[str]
    # - temperature: float
    # - max_tokens: int
    # - system_prompt: str
```

## Output Structure

```
results/bs/{experiment_name}/game{id}/
├── game_results.json       # Winner, rounds, stats
├── messages.jsonl          # All moves with probe scores
├── config.json             # Game configuration
└── visualization.html      # Interactive probe visualization
```

## Limitations

- LLMs may struggle with card tracking (what cards have been played)
- JSON parsing can occasionally fail (falls back to safe defaults)
- No explicit card memory - players rely on reasoning from context

## Future Enhancements

- [ ] Add more sophisticated prompting for card tracking
- [ ] Implement team play variant
- [ ] Add analysis scripts for probe accuracy on bluffs
- [ ] Support for truncated games (limit rounds per rank)
