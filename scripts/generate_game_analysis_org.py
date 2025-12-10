#!/usr/bin/env python3
"""Generate detailed org-mode analysis files for game experiments."""

import json
import statistics
from pathlib import Path
import argparse


def generate_ttl_org(results_dir: Path, output_path: Path):
    """Generate org-mode analysis for TTL experiment."""
    
    batch_results_path = results_dir / "batch_results.json"
    if not batch_results_path.exists():
        print(f"No batch_results.json found in {results_dir}")
        return
    
    with open(batch_results_path) as f:
        batch_data = json.load(f)
    
    org_lines = [
        f"#+TITLE: TTL Experiment: {results_dir.name}",
        f"#+AUTHOR: Auto-generated",
        "",
        "* Overview",
        "",
        f"Results: ~{results_dir}~",
        "",
        f"- Total rounds: {batch_data['total_rounds']}",
        f"- Success rate: {batch_data['success_rate']:.1f}%",
    ]
    
    # Handle both old and new batch_results format
    if 'accuracy_without_probe' in batch_data:
        org_lines.append(f"- Auditor WITHOUT probes: {batch_data['accuracy_without_probe']:.1f}%")
        org_lines.append(f"- Auditor WITH probes: {batch_data['accuracy_with_probe']:.1f}%")
        org_lines.append(f"- *Difference: {batch_data['accuracy_with_probe'] - batch_data['accuracy_without_probe']:+.1f}%*")
    else:
        org_lines.append(f"- Auditor accuracy: {batch_data.get('accuracy', 0):.1f}%")
    
    org_lines.append("")
    
    # Per-game analysis
    org_lines.append("* Games")
    org_lines.append("")
    
    # Handle both 'rounds' and 'round_results' keys
    rounds_data = batch_data.get('rounds') or batch_data.get('round_results', [])
    
    for i, round_result in enumerate(rounds_data, 1):
        org_lines.append(f"** Game {i}")
        org_lines.append("")
        
        game_dir = results_dir / f"game{i}"
        if game_dir.exists():
            org_lines.append(f"[[file:{game_dir}][Results directory]]")
            org_lines.append("")
        
        # Statements
        if 'statements' in round_result:
            org_lines.append("*** Statements")
            org_lines.append("")
            for j, stmt in enumerate(round_result['statements'], 1):
                is_lie = (j == round_result['lie_index'])
                marker = " *[LIE]*" if is_lie else ""
                org_lines.append(f"{j}. {stmt}{marker}")
            org_lines.append("")
        
        # Probe scores table
        if 'probe_scores' in round_result:
            org_lines.append("*** Probe Scores")
            org_lines.append("")
            org_lines.append("| Pos | Deception | Hallucination |")
            org_lines.append("|-----+-----------+---------------|")
            
            probe_scores = round_result['probe_scores']
            
            for pos in ['1', '2', '3']:
                is_lie = (int(pos) == round_result['lie_index'])
                marker = " *" if is_lie else ""
                
                # Try new format: {1: {deception_8b: x, hallucination_8b: y}}
                if pos in probe_scores:
                    scores = probe_scores[pos]
                    dec = scores.get('deception_8b', 0)
                    hal = scores.get('hallucination_8b', 0)
                # Try old format: {deception_8b: {1: x, 2: y}}
                elif 'deception_8b' in probe_scores:
                    dec = probe_scores.get('deception_8b', {}).get(pos, 0)
                    hal = probe_scores.get('hallucination_8b', {}).get(pos, 0)
                else:
                    dec = hal = 0
                
                org_lines.append(f"| {pos}{marker} | {dec:.3f} | {hal:.3f} |")
            
            org_lines.append("")
        
        # Guesses
        org_lines.append("*** Results")
        org_lines.append("")
        
        correct = round_result['lie_index']
        guess_no_probe = round_result.get('auditor_guess_without_probe')
        guess_with_probe = round_result.get('auditor_guess')
        
        if guess_no_probe:
            check = "✓" if guess_no_probe == correct else "✗"
            org_lines.append(f"- No probes: {guess_no_probe} {check}")
        
        if guess_with_probe:
            check = "✓" if guess_with_probe == correct else "✗"
            org_lines.append(f"- With probes: {guess_with_probe} {check}")
        
        org_lines.append("")
        
        viz_file = game_dir / "visualizations" / "consolidated_visualization.html"
        if viz_file.exists():
            org_lines.append(f"[[file:{viz_file}][HTML visualization]]")
            org_lines.append("")
        
        org_lines.append("")
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(org_lines))
    
    print(f"Generated: {output_path}")


def generate_werewolf_org(results_dir: Path, output_path: Path):
    """Generate org-mode analysis for Werewolf experiment."""
    
    org_lines = [
        f"#+TITLE: Werewolf Experiment: {results_dir.name}",
        "",
        "* Overview",
        "",
        f"Results: ~{results_dir}~",
        "",
    ]
    
    game_dirs = sorted([d for d in results_dir.glob("game*") if d.is_dir()])
    org_lines.append(f"Total games: {len(game_dirs)}")
    org_lines.append("")
    org_lines.append("* Games")
    org_lines.append("")
    
    for game_dir in game_dirs:
        game_num = game_dir.name.replace("game", "")
        org_lines.append(f"** Game {game_num}")
        org_lines.append("")
        org_lines.append(f"[[file:{game_dir}][Results directory]]")
        org_lines.append("")
        
        stats_file = game_dir / "game_stats.json"
        if stats_file.exists():
            with open(stats_file) as f:
                stats = json.load(f)
            
            org_lines.append(f"Winner: *{stats['winner']}*")
            org_lines.append(f"Turns: {stats['total_turns']}")
            org_lines.append("")
            
            org_lines.append("*** Players")
            org_lines.append("")
            org_lines.append("| Name | Role | Survived |")
            org_lines.append("|------+------+----------|")
            for player in stats['players']:
                survived = "Yes" if player['survived'] else "No"
                org_lines.append(f"| {player['name']} | {player['role']} | {survived} |")
            org_lines.append("")
            
            viz_file = game_dir / "visualizations" / "consolidated_visualization.html"
            if viz_file.exists():
                org_lines.append(f"[[file:{viz_file}][HTML visualization]]")
                org_lines.append("")
            
            messages_file = game_dir / "messages.md"
            if messages_file.exists():
                org_lines.append(f"[[file:{messages_file}][Readable messages]]")
                org_lines.append("")
        
        org_lines.append("")
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(org_lines))
    
    print(f"Generated: {output_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results_dir", type=Path)
    parser.add_argument("--game-type", choices=["ttl", "werewolf", "cheat"], required=True)
    parser.add_argument("--output", type=Path)
    
    args = parser.parse_args()
    
    output_path = args.output or (args.results_dir / "analysis.org")
    
    if args.game_type == "ttl":
        generate_ttl_org(args.results_dir, output_path)
    elif args.game_type == "werewolf":
        generate_werewolf_org(args.results_dir, output_path)


if __name__ == "__main__":
    main()
