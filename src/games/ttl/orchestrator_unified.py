#!/usr/bin/env python3
"""
Simple orchestrator for TTL (Two Truths and a Lie) game using unified backend.

Runs one round:
1. Deceiver generates 2 truths and 1 lie
2. Deceiver reveals which was the lie
3. Auditor guesses (optionally with probe scores)
"""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.backends import create_backend
from src.player import GamePlayer
from src.result_logging import ResultsLogger

from . import auditor_unified, deceiver_unified
from .config import TTLConfig


def run_game_round(
    config: TTLConfig,
    facts: Optional[List[str]] = None,
    experiment_name: str = "ttl_test",
    round_id: int = 0,
) -> Dict[str, Any]:
    """
    Run a single round of TTL game.

    Args:
        config: TTL game configuration
        facts: Optional list of facts for deceiver to base statements on
               (None for real-world facts mode)
        experiment_name: Name for this experiment (for results directory)
        round_id: Round number for this game

    Returns:
        Dict containing complete game results
    """
    round_start = datetime.now()

    # Create results logger (creates directory structure: results/ttl/{experiment_name}/round{round_id}/)
    logger = ResultsLogger(
        config=config,
        game_name="ttl",
        experiment_base=experiment_name,
        game_id=round_id,
    )
    results_dir = logger.results_dir

    print(f"\n{'=' * 80}")
    print(f"TTL GAME ROUND - {round_start.isoformat()}")
    print(f"{'=' * 80}")
    print(f"Results directory: {results_dir}")
    print()

    # Create deceiver backend and wrap in GamePlayer
    deceiver_backend = create_backend(
        backend_type=config.deceiver_config.backend_type,
        model=config.deceiver_config.model,
        probes=config.deceiver_config.probes,
    )
    deceiver = GamePlayer(
        name=config.deceiver_config.name,
        backend=deceiver_backend,
        system_prompt=config.deceiver_config.system_prompt,
        logger=logger,
    )
    print(f"Deceiver: {config.deceiver_config.backend_type} backend")
    if config.deceiver_config.probes:
        print(f"  Probes: {', '.join(config.deceiver_config.probes)}")

    # Step 1: Deceiver generates statements
    print(f"\n{'─' * 80}")
    if config.use_real_world_facts:
        print("Step 1: Deceiver generating statements from real-world knowledge...")
    else:
        print("Step 1: Deceiver generating statements from provided facts...")
        if facts:
            print(f"  Facts: {facts}")
    print(f"{'─' * 80}\n")

    deceiver_gen = deceiver_unified.generate_statements(
        deceiver,
        config.deceiver_config,
        facts=facts if not config.use_real_world_facts else None,
    )

    if "error" in deceiver_gen:
        return {
            "success": False,
            "error": f"Deceiver generation failed: {deceiver_gen['error']}",
            "round_start": round_start.isoformat(),
        }

    statements = deceiver_gen["statements"]
    print("Generated statements (original order):")
    for i, stmt in enumerate(statements, 1):
        score_str = ""
        if deceiver_gen.get("probe_scores"):
            # Display scores from all probes
            probe_strs = []
            for probe_name, scores in deceiver_gen["probe_scores"].items():
                score = scores.get(i, 0.0)
                probe_strs.append(f"{probe_name}: {score:.3f}")
            if probe_strs:
                score_str = f" [{', '.join(probe_strs)}]"
        print(f"  {i}. {stmt}{score_str}")

    # Shuffle statements so deceiver doesn't know final positions
    # Create mapping: shuffled_position -> original_position
    indices = list(range(3))
    random.shuffle(indices)
    shuffle_mapping = {
        i + 1: indices[i] + 1 for i in range(3)
    }  # {1: 2, 2: 3, 3: 1} means shuffled[1] = original[2]

    # Create shuffled statements and probe scores
    shuffled_statements = [statements[indices[i]] for i in range(3)]
    if deceiver_gen.get("probe_scores"):
        # Map probe scores: shuffled_position gets score from original_position
        # Structure: {probe_name: {shuffled_pos: score}}
        shuffled_probe_scores = {}
        for probe_name, orig_scores in deceiver_gen["probe_scores"].items():
            shuffled_probe_scores[probe_name] = {}
            for shuffled_pos, orig_pos in shuffle_mapping.items():
                if orig_pos in orig_scores:
                    shuffled_probe_scores[probe_name][shuffled_pos] = orig_scores[
                        orig_pos
                    ]
                else:
                    print(
                        f"Warning: Missing {probe_name} score for original position {orig_pos}"
                    )
                    shuffled_probe_scores[probe_name][shuffled_pos] = 0.0
    else:
        shuffled_probe_scores = None

    print(f"\n🔀 Shuffled statement order: {shuffle_mapping}")
    print("Shuffled statements (shown to auditor):")
    for i, stmt in enumerate(shuffled_statements, 1):
        score_str = ""
        if shuffled_probe_scores:
            # Display scores from all probes
            probe_strs = []
            for probe_name, scores in shuffled_probe_scores.items():
                score = scores.get(i, 0.0)
                probe_strs.append(f"{probe_name}: {score:.3f}")
            if probe_strs:
                score_str = f" [{', '.join(probe_strs)}]"
        print(f"  {i}. {stmt}{score_str}")

    # Step 2: Deceiver reveals the lie
    print(f"\n{'─' * 80}")
    print("Step 2: Deceiver revealing which statement was the lie...")
    print(f"{'─' * 80}\n")

    deceiver_reveal = deceiver_unified.reveal_lie(
        deceiver,
        config.deceiver_config,
        statements,  # Use original statements - deceiver doesn't know about shuffle
        facts=facts if not config.use_real_world_facts else None,
    )

    if "error" in deceiver_reveal:
        return {
            "success": False,
            "error": f"Deceiver reveal failed: {deceiver_reveal['error']}",
            "statements": statements,
            "deceiver_generation": deceiver_gen,
            "round_start": round_start.isoformat(),
        }

    revealed_lie = deceiver_reveal["revealed_lie"]
    print(f"Deceiver reveals: Statement {revealed_lie} is the lie")

    # Step 3: Auditor guesses (if configured)
    auditor_results = {}
    if config.auditor_config is not None:
        print(f"\n{'─' * 80}")
        print("Step 3: Auditor making guesses...")
        print(f"{'─' * 80}\n")

        auditor_backend = create_backend(
            backend_type=config.auditor_config.backend_type,
            model=config.auditor_config.model,
            probes=config.auditor_config.probes,
        )
        auditor = GamePlayer(
            name=config.auditor_config.name,
            backend=auditor_backend,
            system_prompt=config.auditor_config.system_prompt,
            logger=logger,
        )

        # Guess without probe scores (using shuffled statements)
        print("  Auditor guess (without probe access):")
        auditor_no_probe = auditor_unified.make_guess(
            auditor,
            config.auditor_config,
            shuffled_statements,
            probe_scores=None,
        )

        if "error" not in auditor_no_probe:
            shuffled_guess = auditor_no_probe["guess"]
            original_guess = shuffle_mapping[shuffled_guess]
            print(
                f"    Guess: Statement {shuffled_guess} (original position {original_guess})"
            )
            auditor_results["without_probe"] = {
                **auditor_no_probe,
                "shuffled_guess": shuffled_guess,
                "original_guess": original_guess,
            }

        # Guess with probe scores (if available, using shuffled statements and scores)
        if shuffled_probe_scores:
            print("\n  Auditor guess (with probe access):")
            auditor_with_probe = auditor_unified.make_guess(
                auditor,
                config.auditor_config,
                shuffled_statements,
                probe_scores=shuffled_probe_scores,
            )

            if "error" not in auditor_with_probe:
                shuffled_guess = auditor_with_probe["guess"]
                original_guess = shuffle_mapping[shuffled_guess]
                print(
                    f"    Guess: Statement {shuffled_guess} (original position {original_guess})"
                )
                auditor_results["with_probe"] = {
                    **auditor_with_probe,
                    "shuffled_guess": shuffled_guess,
                    "original_guess": original_guess,
                }

    # Compile results
    round_end = datetime.now()
    duration = (round_end - round_start).total_seconds()

    results = {
        "success": True,
        "round_start": round_start.isoformat(),
        "round_end": round_end.isoformat(),
        "duration_seconds": duration,
        "results_dir": str(results_dir),
        "config": {
            "use_real_world_facts": config.use_real_world_facts,
            "deceiver_backend": config.deceiver_config.backend_type,
            "deceiver_probes": config.deceiver_config.probes,
        },
        "facts": facts,
        "statements": statements,
        "shuffled_statements": shuffled_statements,
        "shuffle_mapping": shuffle_mapping,
        "deceiver_generation": deceiver_gen,
        "deceiver_reveal": deceiver_reveal,
        "revealed_lie": revealed_lie,
        "auditor_guesses": auditor_results,
    }

    # Calculate accuracy (use original positions)
    if auditor_results:
        print(f"\n{'=' * 80}")
        print("RESULTS")
        print(f"{'=' * 80}\n")
        print(f"Correct answer: Statement {revealed_lie} (original position)")

        if "without_probe" in auditor_results:
            original_guess = auditor_results["without_probe"]["original_guess"]
            correct = original_guess == revealed_lie
            print(
                f"Auditor (no probe): guessed position {original_guess} {'✓ CORRECT' if correct else '✗ WRONG'}"
            )
            results["auditor_correct_without_probe"] = correct

        if "with_probe" in auditor_results:
            original_guess = auditor_results["with_probe"]["original_guess"]
            correct = original_guess == revealed_lie
            print(
                f"Auditor (with probe): guessed position {original_guess} {'✓ CORRECT' if correct else '✗ WRONG'}"
            )
            results["auditor_correct_with_probe"] = correct

    print(f"\nRound duration: {duration:.1f}s")

    # Save results to file
    results_file = results_dir / "game_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {results_file}")

    # Generate consolidated HTML visualization
    viz_file = logger.generate_consolidated_visualization()
    if viz_file:
        print(f"Visualization saved to: {viz_file}")

    # Generate readable markdown format
    markdown_path = logger.generate_readable_messages()
    if markdown_path:
        print(f"Readable messages generated: {markdown_path}")

    return results
