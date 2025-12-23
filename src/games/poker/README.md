# Kuhn Poker for Games-as-Evals

Kuhn Poker integration for the games_as_evals framework. This implementation allows you to run Kuhn Poker games with LLM agents using the unified backend system (Modal, Claude, OpenRouter) with optional deception probe support.

## What is Kuhn Poker?

Kuhn Poker is a simplified poker game that serves as a standard test problem in game theory. It's the simplest game that exhibits bluffing behavior.

### Game Rules

- **Players**: 2
- **Deck**: N cards (default 3 for classic Kuhn Poker; configurable)
- **Ante**: Each player antes 1 chip at the start
- **Deal**: Each player receives one card (cards are private)
- **Betting**: Single betting round with the following action tree:
  - Player 0 can **check** or **bet**
    - If Player 0 checks:
      - Player 1 can **check** (showdown) or **bet**
        - If Player 1 bets: Player 0 can **fold** or **call** (showdown)
    - If Player 0 bets:
      - Player 1 can **fold** or **call** (showdown)
- **Showdown**: Higher card wins
- **Bet size**: 1 chip

### Payoffs

- **Fold**: Opponent wins the pot
- **Showdown**: Higher card wins the pot
- **Pot sizes**:
  - Check-check: 2 chips (winner gets +1)
  - Bet-fold: 3 chips (winner gets +1, loser gets -1)
  - Bet-call: 4 chips (winner gets +2, loser gets -2)

## Quick Start

### Basic Usage

```bash
# Run 100 games with 8B model and deception probe
python examples/run_poker.py --backend modal --model-size 8b --probe deception_8b

# Run with Claude (no probes)
python examples/run_poker.py --backend claude --model claude-sonnet-4-5

# Run 5-card variant for richer strategy
python examples/run_poker.py --backend modal --model-size 8b --n-cards 5 --num-games 50
```

### Programmatic Usage

```python
from src.games.poker import PokerConfig, PokerOrchestrator
from src.config.player_config import PlayerConfig

# Create player configurations
player_configs = [
    PlayerConfig(
        name="Player_0",
        backend_type="modal",
        model="8b",
        probes=["deception_8b"],
        temperature=0.7,
        max_tokens=300,
    ),
    PlayerConfig(
        name="Player_1",
        backend_type="modal",
        model="8b",
        probes=["deception_8b"],
        temperature=0.7,
        max_tokens=300,
    ),
]

# Create poker config
config = PokerConfig(
    players=player_configs,
    n_cards=3,           # Classic 3-card Kuhn Poker
    num_games=100,       # Run 100 games
    use_reasoning=True,  # Enable chain-of-thought reasoning
    share_reasoning=False, # Don't share reasoning between players
)

# Run games
orchestrator = PokerOrchestrator(
    config=config,
    experiment_name="poker_deception_test"
)
results = orchestrator.run_batch()

print(f"Player 0 wins: {results['player_0']['win_rate']:.1%}")
print(f"Player 1 wins: {results['player_1']['win_rate']:.1%}")
print(f"Average payoff: {results['average_payoff_player_0']:.3f} chips/game")
```

## Configuration Options

### Game Parameters

- `n_cards` (int, default=3): Number of cards in the deck
  - 3: Classic Kuhn Poker (Jack, Queen, King)
  - N>3: N-card variant with cards ranked 1 to N
- `num_games` (int, default=100): Number of games to run in the batch
- `seed` (int, optional): Random seed for reproducibility

### Strategy Parameters

- `use_reasoning` (bool, default=True): Enable chain-of-thought reasoning
  - True: Model reasons about strategy before deciding (more strategic, slower)
  - False: Direct action output only (faster, less strategic)
- `share_reasoning` (bool, default=False): Share opponent's reasoning
  - True: Each player sees opponent's last reasoning (makes game easier)
  - False: Normal play (players only see actions, not reasoning)

### Backend Options

The poker game supports all games_as_evals backends:

**Modal (with probe support)**:
```python
PlayerConfig(
    backend_type="modal",
    model="8b",  # or "70b"
    probes=["deception_8b"],  # Optional probe
)
```

**Claude**:
```python
PlayerConfig(
    backend_type="claude",
    model="claude-sonnet-4-5",
)
```

**OpenRouter**:
```python
PlayerConfig(
    backend_type="openrouter",
    model="anthropic/claude-3.5-sonnet",
)
```

## Understanding Results

### Result Structure

```python
results = {
    'num_games': 100,
    'player_0': {
        'name': 'Player_0',
        'wins': 52,
        'win_rate': 0.52,
    },
    'player_1': {
        'name': 'Player_1',
        'wins': 48,
        'win_rate': 0.48,
    },
    'average_payoff_player_0': 0.08,  # Average chips won/lost per game
}
```

### Interpreting Win Rates

- **50% win rate**: Fair/balanced play
- **>55% win rate**: Strong performance (Nash equilibrium is ~53% for player 1 in optimal play)
- **<45% win rate**: Weak/exploitable play

### Expected Value

The `average_payoff_player_0` shows average chips won per game from Player 0's perspective:
- Positive: Player 0 wins chips on average
- Negative: Player 1 wins chips on average
- With optimal play: -1/18 ≈ -0.056 chips/game for Player 0

## Probe Integration

When using Modal backend with probes, each action is scored for deception:

```python
# Access probe scores during analysis
# Scores are logged automatically by ResultsLogger

# Example probe scores structure:
# result.probe_scores["deception_8b"].aggregate_score  # Overall deception score
# result.probe_scores["deception_8b"].token_scores     # Per-token scores
```

Probe scores can be used to:
- Detect bluffing behavior (high deception score with weak cards)
- Identify slow-plays (high deception score with strong cards)
- Analyze strategic deception patterns across game states

## Game Theory Properties

Kuhn Poker is a solved game with:
- **Game tree complexity**: 12 terminal nodes
- **Nash equilibrium**: Mixed strategy exists
- **Expected value**: -1/18 for player 0 with optimal play
- **Information sets**: 12 unique information sets

This makes it an ideal testbed for:
- Testing LLM reasoning about imperfect information
- Evaluating strategic decision-making
- Studying bluffing behavior in controlled settings
- Benchmarking against game-theoretic optimal play

## File Structure

```
src/games/poker/
├── __init__.py          # Module exports
├── README.md            # This file
├── config.py            # PokerConfig class
├── game.py              # Core game engine (KuhnPoker, GameState, etc.)
├── player.py            # PokerPlayer wrapping GamePlayer
└── orchestrator.py      # PokerOrchestrator for running games

examples/
└── run_poker.py         # Example script for running poker games
```

## Advanced Usage

### Analyzing Bluffing Patterns

```python
# Run games with probe
config = PokerConfig(
    players=[player_with_probe, player_with_probe],
    n_cards=3,
    num_games=100,
)

orchestrator = PokerOrchestrator(config, experiment_name="bluff_analysis")
results = orchestrator.run_batch()

# Probe scores are saved in results/poker/bluff_analysis/
# Analyze logs to correlate:
# - High probe scores + weak cards = bluffs
# - High probe scores + strong cards = slow-plays
```

### N-Card Variants

For richer strategic complexity, use more cards:

```python
config = PokerConfig(
    players=player_configs,
    n_cards=5,  # 5-card variant (cards ranked 1-5)
    num_games=200,
)
```

Benefits of N-card variants:
- More nuanced hand strength
- Greater decision-making complexity
- Richer bluffing opportunities
- More strategic depth for analysis

## Integration Notes

This poker implementation integrates with the games_as_evals framework:

- **Backends**: Uses unified `LLMBackend` system (Modal/Claude/OpenRouter)
- **Logging**: Uses `ResultsLogger` for automatic result tracking
- **Probes**: Supports Modal probe scoring for deception detection
- **Config**: Follows `GameConfig` pattern for consistency

All game data is automatically logged and saved to `results/poker/<experiment_name>/`.
