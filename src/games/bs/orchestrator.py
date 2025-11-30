#!/usr/bin/env python3
"""
Main orchestrator for BS (Cheat/I Doubt It) card game.

Runs the full game:
1. Deal cards to all players
2. Players take turns playing cards (truthfully or bluffing)
3. Other players can call BS
4. First player to empty their hand wins
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.backends import create_backend
from src.player import GamePlayer
from src.result_logging import ResultsLogger
from .config import BSConfig
from .game_state import GameState, RANKS
from . import player_actions


def run_game(
    config: BSConfig,
    experiment_name: str = "bs_test",
    game_id: int = 0,
) -> Dict[str, Any]:
    """
    Run a single BS game.

    Args:
        config: BS game configuration
        experiment_name: Name for this experiment
        game_id: Game number for this experiment

    Returns:
        Dict containing complete game results
    """
    game_start = datetime.now()

    # Create results logger
    logger = ResultsLogger(
        config=config,
        game_name="bs",
        experiment_base=experiment_name,
        game_id=game_id
    )
    results_dir = logger.results_dir

    print(f"\n{'=' * 80}")
    print(f"BS CARD GAME - {game_start.isoformat()}")
    print(f"{'=' * 80}")
    print(f"Players: {config.num_players}")
    print(f"Results directory: {results_dir}")
    print()

    # Create players
    players: List[GamePlayer] = []
    for i, player_config in enumerate(config.player_configs):
        backend = create_backend(
            backend_type=player_config.backend_type,
            model=player_config.model,
            probes=player_config.probes if hasattr(player_config, 'probes') else None,
        )
        player = GamePlayer(
            name=player_config.name or f"Player{i}",
            backend=backend,
            system_prompt=player_config.system_prompt,
            logger=logger,
        )
        players.append(player)
        print(f"Player {i}: {player.name} ({player_config.model})")
        if player_config.probes:
            print(f"  Probes: {', '.join(player_config.probes)}")

    print()

    # Initialize game state
    game_state = GameState(num_players=config.num_players)

    print(f"Starting hands:")
    for i, hand in enumerate(game_state.hands):
        print(f"  Player {i}: {len(hand)} cards")
    print()

    # Track play descriptions for history
    play_descriptions = []

    # Game loop
    print(f"{'=' * 80}")
    print("GAME START")
    print(f"{'=' * 80}\n")

    while game_state.round_num < config.max_rounds:
        game_state.round_num += 1
        current_rank = game_state.get_current_rank()
        current_player_idx = game_state.current_player

        print(f"\n{'─' * 80}")
        print(f"Round {game_state.round_num} | Current Rank: {current_rank} | Player {current_player_idx}'s turn")
        print(f"{'─' * 80}")

        # Current player decides what to play
        current_player = players[current_player_idx]
        hand = game_state.hands[current_player_idx]

        print(f"\n{current_player.name} deciding... (hand size: {len(hand)})")

        decision = player_actions.get_play_decision(
            player=current_player,
            config=config.player_configs[current_player_idx],
            hand=hand,
            current_rank=current_rank,
            hand_sizes=game_state.get_hand_sizes(),
            player_idx=current_player_idx,
            recent_plays=play_descriptions,
            allow_passing=config.allow_passing,
        )

        if decision["action"] == "pass":
            print(f"  → {current_player.name} PASSES")
            play_descriptions.append(f"Round {game_state.round_num}: {current_player.name} passed")
            game_state.next_player()
            continue

        # Player is playing cards
        cards_to_play = decision["cards_to_play"]
        claimed_count = decision["claimed_count"]

        if not cards_to_play:
            print(f"  → {current_player.name} has no valid cards to play, PASSES")
            play_descriptions.append(f"Round {game_state.round_num}: {current_player.name} passed")
            game_state.next_player()
            continue

        # Execute play
        action = game_state.play_cards(current_player_idx, current_rank, cards_to_play)

        # Show play with probe scores if available
        actual_cards_str = ", ".join([str(c) for c in cards_to_play])
        truthful_marker = "✓ TRUTHFUL" if action.is_truthful else "✗ BLUFF"

        print(f"  → {current_player.name} plays {claimed_count} card(s) claiming {current_rank}")
        print(f"     Actual cards: {actual_cards_str} [{truthful_marker}]")

        if "reasoning" in decision:
            print(f"     Reasoning: {decision['reasoning']}")

        play_descriptions.append(
            f"Round {game_state.round_num}: {current_player.name} claimed {claimed_count}x {current_rank}"
        )

        # Check for BS calls
        print(f"\n  Checking for BS calls...")
        bs_callers = []

        for i, other_player in enumerate(players):
            if i == current_player_idx:
                continue  # Can't call BS on yourself

            # Ask if they want to call BS
            bs_decision = player_actions.get_bs_call_decision(
                player=other_player,
                config=config.player_configs[i],
                last_play_description=f"{current_player.name} claimed {claimed_count}x {current_rank}",
                hand_sizes=game_state.get_hand_sizes(),
                player_idx=i,
                pile_size=len(game_state.discard_pile),
            )

            if bs_decision["call_bs"]:
                bs_callers.append((i, other_player.name, bs_decision.get("reasoning", "")))

        # Handle BS call
        if bs_callers:
            # First caller challenges
            caller_idx, caller_name, reasoning = bs_callers[0]

            print(f"\n  🚨 {caller_name} calls BS!")
            if reasoning:
                print(f"     Reasoning: {reasoning}")

            # Resolve BS call
            caller_was_correct, loser_idx = game_state.resolve_bs_call(caller_idx)

            if caller_was_correct:
                print(f"     ✓ BS call CORRECT! {current_player.name} was bluffing!")
                print(f"     {current_player.name} picks up {len(game_state.discard_pile)} cards")
            else:
                print(f"     ✗ BS call WRONG! {current_player.name} was truthful!")
                print(f"     {caller_name} picks up {len(game_state.discard_pile)} cards")

            play_descriptions.append(
                f"  → {caller_name} called BS! Result: {'CORRECT' if caller_was_correct else 'WRONG'}"
            )
        else:
            print(f"     No BS calls")

        # Advance to next rank and player
        game_state.advance_rank()
        game_state.next_player()

        # Check win condition
        is_over, winner_idx = game_state.is_game_over()
        if is_over:
            print(f"\n{'=' * 80}")
            print(f"🎉 GAME OVER! {players[winner_idx].name} wins!")
            print(f"{'=' * 80}\n")
            break

        # Show current standings
        print(f"\n  Current hand sizes:")
        for i, size in enumerate(game_state.get_hand_sizes()):
            print(f"    Player {i} ({players[i].name}): {size} cards")

    # Compile results
    game_end = datetime.now()
    duration = (game_end - game_start).total_seconds()

    is_over, winner_idx = game_state.is_game_over()

    results = {
        "success": is_over,
        "winner": winner_idx if is_over else -1,
        "winner_name": players[winner_idx].name if is_over else None,
        "rounds_played": game_state.round_num,
        "game_start": game_start.isoformat(),
        "game_end": game_end.isoformat(),
        "duration_seconds": duration,
        "final_hand_sizes": game_state.get_hand_sizes(),
        "total_plays": len(game_state.play_history),
        "total_bs_calls": sum(1 for desc in play_descriptions if "called BS" in desc),
    }

    # Save results
    results_file = results_dir / "game_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nGame duration: {duration:.1f}s")
    print(f"Results saved to: {results_file}")

    # Generate visualization
    viz_file = logger.generate_consolidated_visualization()
    if viz_file:
        print(f"Visualization saved to: {viz_file}")

    return results
