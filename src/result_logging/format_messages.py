#!/usr/bin/env python3
"""
Format messages.jsonl into a human-readable text file.

Usage:
    python src/scripts/format_messages.py results/cheat/experiment_name/messages.jsonl
"""

import json
import sys
from pathlib import Path


def format_messages(jsonl_path: Path, output_path: Path = None):
    """Convert messages.jsonl to readable markdown format.

    Creates a simple, clean transcript focused on readability.
    Detailed token-by-token analysis is available in the HTML visualization.

    Args:
        jsonl_path: Path to messages.jsonl file
        output_path: Path to output file (default: messages.md in same dir)
    """
    if output_path is None:
        output_path = jsonl_path.parent / "messages.md"

    with open(jsonl_path) as f:
        messages = [json.loads(line) for line in f]

    with open(output_path, "w") as out:
        # Header
        out.write("# Game Transcript\n\n")

        # Player summary
        players = set(msg["player_name"] for msg in messages)
        out.write("**Players:** " + ", ".join(sorted(players)) + "\n")
        out.write(f"**Total messages:** {len(messages)}\n\n")
        out.write("---\n\n")

        # Messages - simple format
        for i, msg in enumerate(messages, 1):
            player = msg["player_name"]

            # Message header with timestamp
            timestamp = msg["timestamp"].split("T")[1].split(".")[0]  # Just HH:MM:SS
            out.write(f"## {i}. {player} [{timestamp}]\n\n")

            # Prompt (if it's substantial - skip empty/system prompts)
            prompt = msg["prompt"].strip()
            if prompt and len(prompt) > 10:
                out.write("**Prompt:**\n\n")
                out.write(f"> {prompt}\n\n")

            # Response
            out.write("**Response:**\n\n")
            out.write(f"{msg['response']}\n\n")

            # Probe scores (summary only - aggregate score)
            if msg.get("probe_scores"):
                out.write("**Probe scores:**\n")
                for probe_name, scores in msg["probe_scores"].items():
                    agg = scores.get("aggregate_score", "N/A")
                    if isinstance(agg, float):
                        out.write(f"- {probe_name}: {agg:.4f}")
                    else:
                        out.write(f"- {probe_name}: {agg}")

                    # Show ground truth if available (from mocks)
                    if scores.get("metadata", {}).get("is_lying") is not None:
                        is_lying = scores["metadata"]["is_lying"]
                        truth_label = "LYING" if is_lying else "HONEST"
                        out.write(f" *[ground truth: {truth_label}]*")
                    out.write("\n")
                out.write("\n")

            out.write("---\n\n")

    print(f"Formatted messages written to: {output_path}")
    print(f"Total messages: {len(messages)}")

    # Print summary statistics
    players = set(msg["player_name"] for msg in messages)
    print(f"\nPlayers: {', '.join(sorted(players))}")
    print(f"Messages per player:")
    for player in sorted(players):
        count = sum(1 for msg in messages if msg["player_name"] == player)
        print(f"  {player}: {count}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python format_messages.py <path/to/messages.jsonl>")
        print("\nExample:")
        print(
            "  python format_messages.py results/cheat/experiment_name/messages.jsonl"
        )
        sys.exit(1)

    jsonl_path = Path(sys.argv[1])

    if not jsonl_path.exists():
        print(f"Error: File not found: {jsonl_path}")
        sys.exit(1)

    if not jsonl_path.name.endswith(".jsonl"):
        print(f"Warning: Expected .jsonl file, got: {jsonl_path.name}")

    format_messages(jsonl_path)


if __name__ == "__main__":
    main()
