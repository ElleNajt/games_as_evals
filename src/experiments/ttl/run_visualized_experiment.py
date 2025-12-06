#!/usr/bin/env python3
"""
Run a TTL experiment with both probes and visualize the results.
"""

import sys
sys.path.insert(0, '/workspace')

from pathlib import Path
from src.config.experiment_config import get_experiment_config
from src.experiments.werewolf.configs import create_werewolf_config
from src.experiments.ttl.configs import create_ttl_config
from src.games.ttl import TTLConfig
from src.games.ttl.orchestrator_unified import run_game_round
from src.visualization.probe_activations import visualize_ttl_game

print('=' * 70)
print('TTL Experiment with Probe Visualization')
print('=' * 70)

# Get 8B experiment config with both probes
exp_config = get_experiment_config('8b_both')

print(f'Model: {exp_config.model}')
print(f'Probes: {exp_config.probes}')
print()

# Create TTL configuration
config_kwargs = exp_config.to_ttl_config_kwargs(use_real_world_facts=True)
config = TTLConfig(**config_kwargs)

# Run a single round
print('Running TTL game...')
results = run_game_round(
    config=config,
    facts=None,
    experiment_name='ttl_visualized',
    round_id=1
)

print()
print('=' * 70)
print('GAME RESULTS')
print('=' * 70)
print(f'Success: {results.get("success", False)}')

if results.get('success'):
    print()
    print('Statements:')
    for i, stmt in enumerate(results['statements'], 1):
        marker = ' <-- LIE' if i-1 == results.get('lie_index') else ''
        print(f'  {i}. {stmt}{marker}')
    
    print()
    print(f'Auditor guessed: {results.get("auditor_guess")}')
    print(f'Auditor correct: {results.get("auditor_correct", False)}')
    
    # Visualize the probe activations
    print()
    print('=' * 70)
    print('CREATING VISUALIZATION')
    print('=' * 70)
    
    result_file = Path('results/ttl/ttl_visualized/game1/game_results.json')
    if result_file.exists():
        visualize_ttl_game(
            game_results_path=result_file,
            vmin=0.0,
            vmax=1.0,
            save_dir=result_file.parent
        )
    else:
        print(f'Result file not found: {result_file}')

print()
print('✓ Experiment complete!')
