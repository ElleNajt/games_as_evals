#!/usr/bin/env python3
"""
Multi-experiment runner for Cheat game.

Runs multiple batch experiments with different configurations and compares results.
Structure:
    results/cheat/multi_experiment_{timestamp}/
        baseline_all_blind/
            game1/, game2/, ...
            batch_results.json
        probe_access_player1/
            game1/, game2/, ...
            batch_results.json
        analysis/
            win_rate_comparison.json
            win_rate_comparison.png
"""

import sys
from pathlib import Path
import json
from datetime import datetime
from typing import List, Dict
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.games.cheat.config import CheatConfig
from src.config.player_config import PlayerConfig
from src.games.cheat.orchestrator import CheatOrchestrator
from src.games.cheat.game_state import deal_cards, PlayerState, CheatGameState
from src.experiments.batch_runner import BatchRunner
from src.player import GamePlayer
from src.result_logging.results_logger import ResultsLogger
from src.backends.base import GenerationResult, ProbeScores, ProbeScoreData
import random


class MockBackend:
    """Mock backend that returns simple responses with mocked probe scores."""
    
    def __init__(self, player_name="MockPlayer"):
        self.player_name = player_name
        self.call_count = 0
    
    def generate(self, messages, max_tokens=512, temperature=0.7):
        """Generate mock responses with probe scores based on the prompt."""
        self.call_count += 1
        
        # Get the last user message
        user_msg = None
        for msg in reversed(messages):
            if msg["role"] == "user":
                user_msg = msg["content"]
                break
        
        # Check if this is a play decision or challenge decision
        is_lying = False
        if "PLAY:" in user_msg and "CARDS:" in user_msg:
            # This is a play decision
            # Lie 70% of the time (randomly pick wrong rank)
            if random.random() < 0.7:
                # Lie - pick a random rank that's not the required one
                ranks = ["Two", "Three", "Four", "Five", "Six", "Seven", 
                        "Eight", "Nine", "Ten", "Jack", "Queen", "King", "Ace"]
                response = f"""PLAY: 1
CARDS: {random.choice(ranks)}"""
                is_lying = True
            else:
                # Tell truth - play Ace (will be corrected by parser)
                response = """PLAY: 1
CARDS: Ace"""
                is_lying = False
                
        elif "CHALLENGE" in user_msg or "PASS" in user_msg:
            # This is a challenge decision
            # If player can see probes, use them to make better decisions
            if "PROBE ANALYSIS" in user_msg:
                # Extract score from prompt (player can see it)
                import re
                # Try deception probe first
                match = re.search(r'Deception score: ([\d.]+)', user_msg)
                if match:
                    score = float(match.group(1))
                    # Challenge if score is high (>0.55 threshold for deception probe player)
                    if score > 0.55:
                        response = "CHALLENGE"
                    else:
                        response = "PASS"
                else:
                    # Try hallucination probe
                    match = re.search(r'Hallucination score: ([\d.]+)', user_msg)
                    if match:
                        score = float(match.group(1))
                        # Hallucination probe is less useful - use higher threshold
                        if score > 0.65:
                            response = "CHALLENGE"
                        else:
                            response = "PASS"
                    else:
                        # Fallback
                        response = "CHALLENGE" if self.call_count % 3 == 0 else "PASS"
            else:
                # No probe access - random challenges (30% of time)
                response = "CHALLENGE" if self.call_count % 3 == 0 else "PASS"
        else:
            response = "I don't understand the question."
        
        # Create mock probe scores if this was a play decision
        probe_scores = None
        tokens = None
        if "PLAY:" in response:
            # Create realistic token list
            tokens = response.split()
            
            # Create mock deception probe scores
            # Higher scores when lying, lower when honest
            if is_lying:
                # High deception scores (0.6-0.9) when lying
                token_scores = [random.uniform(0.6, 0.9) for _ in tokens]
            else:
                # Low deception scores (0.1-0.4) when honest
                token_scores = [random.uniform(0.1, 0.4) for _ in tokens]
            
            aggregate_score = sum(token_scores) / len(token_scores)
            
            # Create both deception and hallucination probe scores
            # For deception: high when lying, low when honest
            # For hallucination: we'll simulate it being less correlated (more random)
            hallucination_scores = [random.uniform(0.3, 0.7) for _ in tokens]
            hallucination_agg = sum(hallucination_scores) / len(hallucination_scores)
            
            probe_scores = ProbeScores(
                scores={
                    "deception_8b": ProbeScoreData(
                        aggregate_score=aggregate_score,
                        token_scores=token_scores,
                        metadata={
                            "probe_type": "deception",
                            "model": "mock",
                            "layer": 12,
                            "num_tokens": len(tokens),
                            "is_lying": is_lying  # Ground truth for testing
                        }
                    ),
                    "hallucination_8b": ProbeScoreData(
                        aggregate_score=hallucination_agg,
                        token_scores=hallucination_scores,
                        metadata={
                            "probe_type": "hallucination",
                            "model": "mock",
                            "layer": 12,
                            "num_tokens": len(tokens),
                            "is_lying": is_lying  # Ground truth for testing
                        }
                    )
                }
            )
        else:
            probe_scores = None
        
        return GenerationResult(
            text=response,
            tokens=tokens,
            top_k_logits=None,
            probe_scores=probe_scores
        )


def run_cheat_game_with_mocks(config, round_id, experiment_name, **kwargs):
    """Run a single Cheat game with mocked backends."""
    # Set up game state manually
    hands = deal_cards(config.num_players, config.num_decks)
    player_states = [
        PlayerState(name=config.players[i].name, hand=hands[i])
        for i in range(config.num_players)
    ]
    state = CheatGameState(players=player_states)
    
    # Set up logger
    logger = ResultsLogger(
        config=config,
        game_name="cheat",
        experiment_base=experiment_name,
        game_id=round_id
    )
    
    # Create players with mock backends
    game_players = []
    for player_config in config.players:
        backend = MockBackend(player_name=player_config.name)
        player = GamePlayer(
            name=player_config.name,
            backend=backend,
            system_prompt=player_config.system_prompt,
            logger=logger
        )
        game_players.append(player)
    
    # Create orchestrator and inject the mocked components
    orchestrator = CheatOrchestrator(config, experiment_name=experiment_name, game_id=round_id)
    orchestrator.state = state
    orchestrator.players = game_players
    orchestrator.logger = logger
    
    # Log initial state
    logger.log_game_event('game_start', {
        'num_players': config.num_players,
        'num_decks': config.num_decks,
        'round_id': round_id,
    })
    
    # Run the game loop
    turn_count = 0
    while not state.game_over and turn_count < config.max_turns:
        orchestrator._play_turn()
        turn_count += 1
        
        # Check for winner
        winner = state.check_winner()
        if winner:
            break
    
    # Finalize
    results = orchestrator._finalize_game()
    return results


def extract_cheat_stats(game_result):
    """Extract key statistics from a Cheat game result."""
    return {
        'winner': game_result.get('winner'),
        'total_turns': game_result.get('total_turns'),
        'final_hands': game_result.get('final_hands', {}),
    }


def create_baseline_config() -> CheatConfig:
    """All players baseline - no probe access."""
    players = [
        PlayerConfig(
            name="Player_1",
            backend_type="mock",
            model="mock",
            can_see_probes=False,
            system_prompt="You are a card game player."
        ),
        PlayerConfig(
            name="Player_2",
            backend_type="mock",
            model="mock",
            can_see_probes=False,
            system_prompt="You are a card game player."
        ),
        PlayerConfig(
            name="Player_3",
            backend_type="mock",
            model="mock",
            can_see_probes=False,
            system_prompt="You are a card game player."
        ),
        PlayerConfig(
            name="Player_4",
            backend_type="mock",
            model="mock",
            can_see_probes=False,
            system_prompt="You are a card game player."
        )
    ]
    
    config = CheatConfig(
        num_players=4,
        num_decks=1,
        max_turns=20,
        provide_probe_scores=False  # No probes at all
    )
    config.players = players
    return config


def create_deception_probe_config() -> CheatConfig:
    """Player 1 has deception probe access, others are baseline."""
    players = [
        PlayerConfig(
            name="Player_1_DECEPTION",
            backend_type="mock",
            model="mock",
            probes=["deception_8b"],
            can_see_probes=True,
            system_prompt="You are a card game player with deception detection."
        ),
        PlayerConfig(
            name="Player_2",
            backend_type="mock",
            model="mock",
            can_see_probes=False,
            system_prompt="You are a card game player."
        ),
        PlayerConfig(
            name="Player_3",
            backend_type="mock",
            model="mock",
            can_see_probes=False,
            system_prompt="You are a card game player."
        ),
        PlayerConfig(
            name="Player_4",
            backend_type="mock",
            model="mock",
            can_see_probes=False,
            system_prompt="You are a card game player."
        )
    ]
    
    config = CheatConfig(
        num_players=4,
        num_decks=1,
        max_turns=20,
        provide_probe_scores=True
    )
    config.players = players
    return config


def create_hallucination_probe_config() -> CheatConfig:
    """Player 1 has hallucination probe access, others are baseline."""
    players = [
        PlayerConfig(
            name="Player_1_HALLUCINATION",
            backend_type="mock",
            model="mock",
            probes=["hallucination_8b"],
            can_see_probes=True,
            system_prompt="You are a card game player with hallucination detection."
        ),
        PlayerConfig(
            name="Player_2",
            backend_type="mock",
            model="mock",
            can_see_probes=False,
            system_prompt="You are a card game player."
        ),
        PlayerConfig(
            name="Player_3",
            backend_type="mock",
            model="mock",
            can_see_probes=False,
            system_prompt="You are a card game player."
        ),
        PlayerConfig(
            name="Player_4",
            backend_type="mock",
            model="mock",
            can_see_probes=False,
            system_prompt="You are a card game player."
        )
    ]
    
    config = CheatConfig(
        num_players=4,
        num_decks=1,
        max_turns=20,
        provide_probe_scores=True
    )
    config.players = players
    return config


def run_multi_experiment(num_rounds: int = 10):
    """Run multiple experiments and analyze results."""
    # Create multi-experiment directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    multi_exp_name = f"multi_experiment_{timestamp}"
    
    # Get git hash for tracking
    hash_result = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode().strip()
    multi_exp_name = f"multi_experiment_{hash_result}_{timestamp}"
    
    results_dir = Path("results/cheat") / multi_exp_name
    results_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*80)
    print(f"MULTI-EXPERIMENT RUNNER")
    print(f"Results directory: {results_dir}")
    print(f"Number of rounds per experiment: {num_rounds}")
    print("="*80)
    
    # Store experiment results for cross-analysis
    experiment_results = []
    
    # Experiment 1: Baseline (all players blind)
    print("\n" + "="*80)
    print("EXPERIMENT 1: BASELINE (No probe access)")
    print("="*80)
    
    baseline_config = create_baseline_config()
    baseline_exp_name = "baseline_all_blind"
    
    baseline_batch_runner = BatchRunner(
        game_name='cheat',
        run_game_fn=lambda **kwargs: run_cheat_game_with_mocks(baseline_config, **kwargs),
        extract_stats_fn=extract_cheat_stats,
    )
    
    baseline_results = baseline_batch_runner.run_batch(
        num_rounds=num_rounds,
        experiment_name=f"{multi_exp_name}/{baseline_exp_name}",
        save_results=True,
        verbose=True
    )
    
    experiment_results.append({
        'name': baseline_exp_name,
        'description': 'All players baseline - no probe access',
        'results': baseline_results.to_dict()
    })
    
    # Experiment 2: Player 1 has deception probe access
    print("\n" + "="*80)
    print("EXPERIMENT 2: DECEPTION PROBE (Player 1 can see deception probes)")
    print("="*80)
    
    deception_config = create_deception_probe_config()
    deception_exp_name = "deception_probe_player1"
    
    deception_batch_runner = BatchRunner(
        game_name='cheat',
        run_game_fn=lambda **kwargs: run_cheat_game_with_mocks(deception_config, **kwargs),
        extract_stats_fn=extract_cheat_stats,
    )
    
    deception_results = deception_batch_runner.run_batch(
        num_rounds=num_rounds,
        experiment_name=f"{multi_exp_name}/{deception_exp_name}",
        save_results=True,
        verbose=True
    )
    
    experiment_results.append({
        'name': deception_exp_name,
        'description': 'Player 1 has deception probe access, others baseline',
        'results': deception_results.to_dict()
    })
    
    # Experiment 3: Player 1 has hallucination probe access
    print("\n" + "="*80)
    print("EXPERIMENT 3: HALLUCINATION PROBE (Player 1 can see hallucination probes)")
    print("="*80)
    
    hallucination_config = create_hallucination_probe_config()
    hallucination_exp_name = "hallucination_probe_player1"
    
    hallucination_batch_runner = BatchRunner(
        game_name='cheat',
        run_game_fn=lambda **kwargs: run_cheat_game_with_mocks(hallucination_config, **kwargs),
        extract_stats_fn=extract_cheat_stats,
    )
    
    hallucination_results = hallucination_batch_runner.run_batch(
        num_rounds=num_rounds,
        experiment_name=f"{multi_exp_name}/{hallucination_exp_name}",
        save_results=True,
        verbose=True
    )
    
    experiment_results.append({
        'name': hallucination_exp_name,
        'description': 'Player 1 has hallucination probe access, others baseline',
        'results': hallucination_results.to_dict()
    })
    
    # Create analysis directory
    analysis_dir = results_dir / "analysis"
    analysis_dir.mkdir(exist_ok=True)
    
    # Run cross-experiment analysis
    print("\n" + "="*80)
    print("CROSS-EXPERIMENT ANALYSIS")
    print("="*80)
    
    analysis_results = analyze_experiments(experiment_results)
    
    # Save analysis results
    analysis_file = analysis_dir / "win_rate_comparison.json"
    with open(analysis_file, 'w') as f:
        json.dump(analysis_results, f, indent=2)
    
    print(f"\nAnalysis saved to: {analysis_file}")
    
    # Generate visualization
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        # Plot 1: Win rates by experiment
        ax1 = axes[0]
        exp_names = [exp['name'] for exp in experiment_results]
        
        # Get all unique player names across experiments
        all_players = set()
        for exp in experiment_results:
            all_players.update(exp['results']['aggregated_stats']['win_rates'].keys())
        
        players = sorted(all_players)
        x = np.arange(len(exp_names))
        width = 0.2
        
        for i, player in enumerate(players):
            win_rates = []
            for exp in experiment_results:
                rate = exp['results']['aggregated_stats']['win_rates'].get(player, 0.0)
                win_rates.append(rate * 100)  # Convert to percentage
            
            ax1.bar(x + i * width, win_rates, width, label=player)
        
        ax1.set_xlabel('Experiment', fontsize=12)
        ax1.set_ylabel('Win Rate (%)', fontsize=12)
        ax1.set_title('Win Rates by Experiment', fontsize=14, fontweight='bold')
        ax1.set_xticks(x + width * (len(players) - 1) / 2)
        ax1.set_xticklabels([exp.replace('_', '\n') for exp in exp_names], fontsize=10)
        ax1.legend()
        ax1.grid(axis='y', alpha=0.3)
        
        # Plot 2: Success rate comparison
        ax2 = axes[1]
        success_rates = [exp['results']['success_rate'] for exp in experiment_results]
        colors = ['#2ecc71', '#3498db', '#e74c3c']  # green, blue, red
        
        ax2.bar(exp_names, success_rates, color=colors[:len(exp_names)], alpha=0.7)
        ax2.set_xlabel('Experiment', fontsize=12)
        ax2.set_ylabel('Success Rate (%)', fontsize=12)
        ax2.set_title('Experiment Success Rates', fontsize=14, fontweight='bold')
        ax2.set_xticklabels([exp.replace('_', '\n') for exp in exp_names], fontsize=10)
        ax2.set_ylim([0, 105])
        ax2.grid(axis='y', alpha=0.3)
        
        # Add value labels on bars
        for i, v in enumerate(success_rates):
            ax2.text(i, v + 2, f'{v:.1f}%', ha='center', va='bottom', fontweight='bold')
        
        plt.tight_layout()
        
        plot_file = analysis_dir / "win_rate_comparison.png"
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        print(f"Visualization saved to: {plot_file}")
        
    except ImportError:
        print("matplotlib not available - skipping visualization")
    
    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    for exp in experiment_results:
        print(f"\n{exp['name']}:")
        print(f"  Description: {exp['description']}")
        print(f"  Success rate: {exp['results']['success_rate']:.1f}%")
        print(f"  Win rates:")
        for player, rate in exp['results']['aggregated_stats']['win_rates'].items():
            print(f"    {player}: {rate*100:.1f}%")
    
    print(f"\nAll results saved to: {results_dir}")
    print("="*80)
    
    return results_dir


def analyze_experiments(experiment_results: List[Dict]) -> Dict:
    """Analyze results across multiple experiments."""
    analysis = {
        'num_experiments': len(experiment_results),
        'experiments': [],
        'comparison': {}
    }
    
    for exp in experiment_results:
        exp_analysis = {
            'name': exp['name'],
            'description': exp['description'],
            'total_rounds': exp['results']['total_rounds'],
            'successful_rounds': exp['results']['successful_rounds'],
            'success_rate': exp['results']['success_rate'],
            'win_rates': exp['results']['aggregated_stats']['win_rates'],
            'avg_turns': exp['results']['aggregated_stats'].get('total_turns_mean', 0)
        }
        analysis['experiments'].append(exp_analysis)
    
    # Compare baseline vs probe access (both types)
    if len(experiment_results) >= 3:
        baseline = experiment_results[0]
        deception_exp = experiment_results[1]
        hallucination_exp = experiment_results[2]
        
        baseline_wins = baseline['results']['aggregated_stats']['win_rates']
        deception_wins = deception_exp['results']['aggregated_stats']['win_rates']
        hallucination_wins = hallucination_exp['results']['aggregated_stats']['win_rates']
        
        # Get Player_1's win rate in baseline
        baseline_p1_rate = baseline_wins.get("Player_1", 0.0)
        
        # Get probe players' win rates
        deception_player = next((p for p in deception_wins.keys() if "DECEPTION" in p), None)
        hallucination_player = next((p for p in hallucination_wins.keys() if "HALLUCINATION" in p), None)
        
        analysis['comparison'] = {
            'baseline_player1_rate': baseline_p1_rate,
            'deception_probe': {
                'player': deception_player,
                'win_rate': deception_wins.get(deception_player, 0.0) if deception_player else 0.0,
                'improvement': (deception_wins.get(deception_player, 0.0) - baseline_p1_rate) if deception_player else 0.0
            },
            'hallucination_probe': {
                'player': hallucination_player,
                'win_rate': hallucination_wins.get(hallucination_player, 0.0) if hallucination_player else 0.0,
                'improvement': (hallucination_wins.get(hallucination_player, 0.0) - baseline_p1_rate) if hallucination_player else 0.0
            }
        }
    
    return analysis


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run multi-experiment Cheat game analysis")
    parser.add_argument("--rounds", type=int, default=10, help="Number of rounds per experiment")
    args = parser.parse_args()
    
    run_multi_experiment(num_rounds=args.rounds)
