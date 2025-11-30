#!/usr/bin/env python3
"""
Comprehensive TTL experiment analysis with probe accuracy assessment.

Can analyze a single experiment OR compare baseline vs CoT.

Usage:
    # Single experiment analysis
    python src/scripts/analysis/analyze_ttl_experiments.py results/ttl/ttl_70b_8b_baseline

    # Compare baseline vs CoT
    python src/scripts/analysis/analyze_ttl_experiments.py \
        --baseline results/ttl/ttl_70b_8b_baseline \
        --cot results/ttl/ttl_70b_8b_cot
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
import statistics


class TTLExperimentAnalyzer:
    """Unified analyzer for TTL experiments."""

    def __init__(self, results_dir: Path, name: str = "Experiment"):
        self.results_dir = Path(results_dir)
        self.name = name
        self.rounds = []
        self._load_data()

    def _load_data(self):
        """Load all round data."""
        for round_dir in sorted(self.results_dir.glob("round*")):
            round_data = {"round_id": round_dir.name}

            # Load game results
            game_results_file = round_dir / "game_results.json"
            if game_results_file.exists():
                with open(game_results_file) as f:
                    round_data["game_results"] = json.load(f)

            # Load messages with probe scores
            messages_file = round_dir / "messages.jsonl"
            if messages_file.exists():
                messages = []
                with open(messages_file) as f:
                    for line in f:
                        messages.append(json.loads(line))
                round_data["messages"] = messages

            self.rounds.append(round_data)

    def get_probe_accuracy(self) -> Dict:
        """Calculate probe accuracy metrics."""
        probe_data = defaultdict(lambda: {
            "predictions": [],
            "lie_scores": [],
            "truth_scores": [],
        })

        for round_data in self.rounds:
            game_results = round_data.get("game_results", {})
            if not game_results.get("success"):
                continue

            revealed_lie = game_results.get("revealed_lie")
            if not revealed_lie:
                continue

            deceiver_gen = game_results.get("deceiver_generation", {})
            probe_scores = deceiver_gen.get("probe_scores", {})
            statements = deceiver_gen.get("statements", [])

            for probe_name, statement_scores in probe_scores.items():
                if not statement_scores:
                    continue

                # Predict: statement with highest probe score
                predicted_lie = max(statement_scores.items(), key=lambda x: x[1])[0]
                correct = (predicted_lie == revealed_lie)

                lie_score = statement_scores.get(revealed_lie, 0.0)
                truth_scores = [score for stmt_num, score in statement_scores.items()
                              if stmt_num != revealed_lie]

                probe_data[probe_name]["predictions"].append({
                    "round": round_data["round_id"],
                    "predicted": predicted_lie,
                    "actual": revealed_lie,
                    "correct": correct,
                    "lie_score": lie_score,
                    "truth_scores": truth_scores,
                    "all_scores": statement_scores,
                    "statements": statements,
                })
                probe_data[probe_name]["lie_scores"].append(lie_score)
                probe_data[probe_name]["truth_scores"].extend(truth_scores)

        # Calculate metrics
        results = {}
        for probe_name, data in probe_data.items():
            predictions = data["predictions"]
            if not predictions:
                continue

            correct_count = sum(1 for p in predictions if p["correct"])
            accuracy = correct_count / len(predictions)

            results[probe_name] = {
                "accuracy": accuracy,
                "correct": correct_count,
                "total": len(predictions),
                "avg_lie_score": statistics.mean(data["lie_scores"]),
                "avg_truth_score": statistics.mean(data["truth_scores"]),
                "separation": statistics.mean(data["lie_scores"]) - statistics.mean(data["truth_scores"]),
                "predictions": predictions,
            }

        return results

    def get_auditor_performance(self) -> Dict:
        """Calculate auditor accuracy."""
        with_probe = []
        without_probe = []

        for round_data in self.rounds:
            game_results = round_data.get("game_results", {})
            if not game_results.get("success"):
                continue

            if "auditor_correct_with_probe" in game_results:
                with_probe.append(game_results["auditor_correct_with_probe"])

            if "auditor_correct_without_probe" in game_results:
                without_probe.append(game_results["auditor_correct_without_probe"])

        results = {}
        if with_probe:
            correct = sum(1 for x in with_probe if x)
            results["with_probe"] = {
                "accuracy": correct / len(with_probe),
                "correct": correct,
                "total": len(with_probe),
            }

        if without_probe:
            correct = sum(1 for x in without_probe if x)
            results["without_probe"] = {
                "accuracy": correct / len(without_probe),
                "correct": correct,
                "total": len(without_probe),
            }

        return results

    def get_cot_analysis(self) -> Dict:
        """Analyze probe scores on CoT reasoning vs answers."""
        results = defaultdict(lambda: defaultdict(list))

        for round_data in self.rounds:
            for msg in round_data.get("messages", []):
                player = msg.get("player_name", "")
                response = msg.get("response", "")
                tokens = msg.get("tokens", [])
                probe_scores_dict = msg.get("probe_scores", {})

                if not probe_scores_dict or not tokens:
                    continue

                # Check for CoT pattern
                if len(tokens) > 50 or "FINAL ANSWER:" in response:
                    reasoning_end_idx = None

                    if "FINAL ANSWER:" in response:
                        split_point = response.index("FINAL ANSWER:")
                        reasoning_end_idx = int(len(tokens) * (split_point / len(response)))

                    for probe_name, probe_data in probe_scores_dict.items():
                        token_scores = probe_data.get("token_scores", [])
                        if not token_scores:
                            continue

                        if reasoning_end_idx and reasoning_end_idx > 0:
                            reasoning_scores = token_scores[:reasoning_end_idx]
                            answer_scores = token_scores[reasoning_end_idx:]

                            if reasoning_scores and answer_scores:
                                results[player][probe_name].append({
                                    "avg_reasoning": statistics.mean(reasoning_scores),
                                    "avg_answer": statistics.mean(answer_scores),
                                    "delta": statistics.mean(answer_scores) - statistics.mean(reasoning_scores),
                                })

        return dict(results)


def print_section_header(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80 + "\n")


def analyze_single_experiment(analyzer: TTLExperimentAnalyzer):
    """Detailed analysis of a single experiment."""
    print_section_header(f"ANALYSIS: {analyzer.name}")

    print(f"Directory: {analyzer.results_dir}")
    print(f"Rounds analyzed: {len(analyzer.rounds)}\n")

    # 1. Probe Accuracy
    print_section_header("PROBE ACCURACY")
    print("Do high probe scores correctly identify lies?\n")

    probe_acc = analyzer.get_probe_accuracy()

    if not probe_acc:
        print("No probe data found.\n")
    else:
        for probe_name, metrics in sorted(probe_acc.items()):
            print(f"{probe_name}:")
            print(f"  Accuracy: {metrics['accuracy']:.1%} ({metrics['correct']}/{metrics['total']})")
            print(f"  Avg score on LIES:   {metrics['avg_lie_score']:.3f}")
            print(f"  Avg score on TRUTHS: {metrics['avg_truth_score']:.3f}")
            print(f"  Separation:          {metrics['separation']:.3f}")

            if metrics['separation'] > 0.1:
                print(f"  → ✓ Good separation - probe distinguishes lies from truths")
            elif metrics['separation'] > 0:
                print(f"  → ~ Weak separation")
            else:
                print(f"  → ✗ Poor separation - probe doesn't distinguish lies")

            # Show some failures
            failures = [p for p in metrics["predictions"] if not p["correct"]]
            if failures:
                print(f"\n  Failed predictions ({len(failures)}/{metrics['total']}):")
                for fail in failures[:3]:
                    print(f"    {fail['round']}: Predicted {fail['predicted']}, Actual {fail['actual']}")
                    print(f"      Scores: {fail['all_scores']}")
                if len(failures) > 3:
                    print(f"    ... and {len(failures) - 3} more")
            print()

    # 2. Auditor Performance
    print_section_header("AUDITOR PERFORMANCE")

    auditor_perf = analyzer.get_auditor_performance()

    if not auditor_perf:
        print("No auditor data found.\n")
    else:
        for condition, metrics in auditor_perf.items():
            print(f"{condition.replace('_', ' ').title()}:")
            print(f"  Accuracy: {metrics['accuracy']:.1%} ({metrics['correct']}/{metrics['total']})")

        if "with_probe" in auditor_perf and "without_probe" in auditor_perf:
            delta = auditor_perf["with_probe"]["accuracy"] - auditor_perf["without_probe"]["accuracy"]
            print(f"\nProbe benefit: {delta:+.1%}")
            if delta > 0.05:
                print("  → ✓ Probes help significantly")
            elif delta > 0:
                print("  → ~ Probes help slightly")
            else:
                print("  → ✗ Probes don't help")
        print()

    # 3. CoT Analysis
    print_section_header("CHAIN-OF-THOUGHT ANALYSIS")

    cot = analyzer.get_cot_analysis()

    if not cot:
        print("No CoT data found (likely baseline experiment).\n")
    else:
        for player, probes in cot.items():
            print(f"{player}:")
            for probe_name, rounds in probes.items():
                if rounds:
                    avg_reasoning = statistics.mean([r["avg_reasoning"] for r in rounds])
                    avg_answer = statistics.mean([r["avg_answer"] for r in rounds])
                    avg_delta = statistics.mean([r["delta"] for r in rounds])

                    print(f"  {probe_name}:")
                    print(f"    During reasoning: {avg_reasoning:.3f}")
                    print(f"    During answer:    {avg_answer:.3f}")
                    print(f"    Δ (answer-reasoning): {avg_delta:+.3f}")

                    if avg_delta > 0.05:
                        print(f"      → Probe scores INCREASE in answer")
                    elif avg_delta < -0.05:
                        print(f"      → Probe scores DECREASE in answer")
                    else:
                        print(f"      → Probe scores stable")
            print()


def compare_experiments(baseline: TTLExperimentAnalyzer, cot: TTLExperimentAnalyzer):
    """Compare baseline vs CoT experiments."""
    print_section_header("COMPARISON: Baseline vs Chain-of-Thought")

    print(f"Baseline: {baseline.results_dir} ({len(baseline.rounds)} rounds)")
    print(f"CoT:      {cot.results_dir} ({len(cot.rounds)} rounds)\n")

    # 1. Probe Accuracy Comparison
    print_section_header("PROBE ACCURACY COMPARISON")

    baseline_probes = baseline.get_probe_accuracy()
    cot_probes = cot.get_probe_accuracy()

    all_probe_names = set(baseline_probes.keys()) | set(cot_probes.keys())

    print(f"{'Probe':<25} {'Baseline':<15} {'CoT':<15} {'Change':<10}")
    print("-" * 80)

    for probe_name in sorted(all_probe_names):
        baseline_acc = baseline_probes.get(probe_name, {}).get("accuracy", 0)
        cot_acc = cot_probes.get(probe_name, {}).get("accuracy", 0)
        change = cot_acc - baseline_acc

        print(f"{probe_name:<25} {baseline_acc:<15.1%} {cot_acc:<15.1%} {change:+.1%}")

    print()

    # 2. Auditor Performance Comparison
    print_section_header("AUDITOR PERFORMANCE COMPARISON")

    baseline_aud = baseline.get_auditor_performance()
    cot_aud = cot.get_auditor_performance()

    print(f"{'Condition':<25} {'Baseline':<15} {'CoT':<15} {'Improvement':<10}")
    print("-" * 80)

    for condition in ["without_probe", "with_probe"]:
        if condition in baseline_aud and condition in cot_aud:
            baseline_acc = baseline_aud[condition]["accuracy"]
            cot_acc = cot_aud[condition]["accuracy"]
            improvement = cot_acc - baseline_acc

            print(f"{condition.replace('_', ' ').title():<25} {baseline_acc:<15.1%} {cot_acc:<15.1%} {improvement:+.1%}")

    print()

    # 3. Key Findings
    print_section_header("KEY FINDINGS")

    # Best probe
    if baseline_probes:
        best = max(baseline_probes.items(), key=lambda x: x[1]["accuracy"])
        print(f"✓ Most accurate probe: {best[0]} ({best[1]['accuracy']:.1%})")

    # CoT impact on auditor
    if "without_probe" in baseline_aud and "without_probe" in cot_aud:
        baseline_acc = baseline_aud["without_probe"]["accuracy"]
        cot_acc = cot_aud["without_probe"]["accuracy"]
        improvement = cot_acc - baseline_acc

        if improvement > 0.05:
            print(f"✓ CoT improves auditor by {improvement:.1%} (without probes)")
        elif improvement > 0:
            print(f"~ CoT slightly improves auditor by {improvement:.1%} (without probes)")
        else:
            print(f"✗ CoT doesn't improve auditor ({improvement:+.1%}) (without probes)")

    # Probe value
    if "with_probe" in baseline_aud and "without_probe" in baseline_aud:
        delta = baseline_aud["with_probe"]["accuracy"] - baseline_aud["without_probe"]["accuracy"]
        print(f"✓ Probe access improves auditor by {delta:.1%} (baseline)")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Analyze TTL experiments with probe accuracy assessment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single experiment analysis
  python analyze_ttl_experiments.py results/ttl/experiment1

  # Compare baseline vs CoT
  python analyze_ttl_experiments.py \\
      --baseline results/ttl/baseline \\
      --cot results/ttl/cot
        """
    )

    parser.add_argument("experiment", nargs="?", type=str,
                       help="Single experiment directory to analyze")
    parser.add_argument("--baseline", type=str,
                       help="Baseline experiment directory (for comparison)")
    parser.add_argument("--cot", type=str,
                       help="CoT experiment directory (for comparison)")

    args = parser.parse_args()

    # Validate arguments
    if args.baseline and args.cot:
        # Comparison mode
        baseline_dir = Path(args.baseline)
        cot_dir = Path(args.cot)

        if not baseline_dir.exists():
            print(f"Error: Baseline directory not found: {baseline_dir}")
            return
        if not cot_dir.exists():
            print(f"Error: CoT directory not found: {cot_dir}")
            return

        baseline = TTLExperimentAnalyzer(baseline_dir, "Baseline")
        cot_exp = TTLExperimentAnalyzer(cot_dir, "CoT")
        compare_experiments(baseline, cot_exp)

    elif args.experiment:
        # Single experiment mode
        exp_dir = Path(args.experiment)

        if not exp_dir.exists():
            print(f"Error: Experiment directory not found: {exp_dir}")
            return

        analyzer = TTLExperimentAnalyzer(exp_dir, exp_dir.name)
        analyze_single_experiment(analyzer)

    else:
        parser.print_help()
        return


if __name__ == "__main__":
    main()
