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
    
    Args:
        jsonl_path: Path to messages.jsonl file
        output_path: Path to output file (default: messages.md in same dir)
    """
    if output_path is None:
        output_path = jsonl_path.parent / "messages.md"
    
    with open(jsonl_path) as f:
        messages = [json.loads(line) for line in f]
    
    with open(output_path, 'w') as out:
        # Header
        out.write("# Game Messages - Readable Format\n\n")
        out.write(f"**Source:** `{jsonl_path}`\n\n")
        out.write(f"**Total messages:** {len(messages)}\n\n")
        
        # Player summary
        players = set(msg['player_name'] for msg in messages)
        out.write("## Players\n\n")
        for player in sorted(players):
            count = sum(1 for msg in messages if msg['player_name'] == player)
            out.write(f"- **{player}**: {count} messages\n")
        out.write("\n---\n\n")
        
        # Messages
        out.write("## Messages\n\n")
        
        for i, msg in enumerate(messages, 1):
            # Message header
            out.write(f"### Message {i}: {msg['player_name']}\n\n")
            out.write(f"**Timestamp:** {msg['timestamp']}\n\n")
            
            # Prompt
            out.write("#### Prompt\n\n")
            out.write("```\n")
            out.write(msg['prompt'])
            out.write("\n```\n\n")
            
            # Response
            out.write("#### Response\n\n")
            out.write("```\n")
            out.write(msg['response'])
            out.write("\n```\n\n")
            
            # Probe scores if present
            if msg.get('probe_scores'):
                out.write("#### Probe Scores\n\n")
                for probe_name, scores in msg['probe_scores'].items():
                    out.write(f"**{probe_name}:**\n\n")
                    out.write(f"- Aggregate score: `{scores.get('aggregate_score', 'N/A')}`\n")
                    
                    # Show metadata if present
                    if scores.get('metadata'):
                        metadata = scores['metadata']
                        if 'num_tokens' in metadata:
                            out.write(f"- Tokens scored: {metadata['num_tokens']}\n")
                        
                        # Show ground truth if available (from mocks)
                        if 'is_lying' in metadata:
                            ground_truth = "LYING" if metadata['is_lying'] else "HONEST"
                            out.write(f"- **Ground truth:** {ground_truth}\n")
                    
                    # Show a few token scores as examples
                    if scores.get('token_scores'):
                        token_scores = scores['token_scores']
                        first_five = [f"{s:.3f}" for s in token_scores[:5]]
                        out.write(f"- Token scores (first 5): `{first_five}`\n")
                        out.write(f"- Token scores range: `{min(token_scores):.3f}` to `{max(token_scores):.3f}`\n")
                    out.write("\n")
            
            # Tokens if present
            if msg.get('tokens'):
                out.write("#### Tokens\n\n")
                out.write(f"**Total:** {len(msg['tokens'])}\n\n")
                out.write("```\n")
                out.write(" ".join(msg['tokens'][:20]))
                if len(msg['tokens']) > 20:
                    out.write(" ...")
                out.write("\n```\n\n")
            
            # Metadata
            if msg.get('metadata'):
                out.write("<details>\n")
                out.write("<summary>Metadata</summary>\n\n")
                out.write("```json\n")
                for key, value in msg['metadata'].items():
                    if key == 'system_prompt':
                        out.write(f'"{key}": "[truncated, {len(value)} chars]"\n')
                    else:
                        out.write(f'"{key}": {json.dumps(value)}\n')
                out.write("```\n\n")
                out.write("</details>\n\n")
            
            out.write("---\n\n")
    
    print(f"Formatted messages written to: {output_path}")
    print(f"Total messages: {len(messages)}")
    
    # Print summary statistics
    players = set(msg['player_name'] for msg in messages)
    print(f"\nPlayers: {', '.join(sorted(players))}")
    print(f"Messages per player:")
    for player in sorted(players):
        count = sum(1 for msg in messages if msg['player_name'] == player)
        print(f"  {player}: {count}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python format_messages.py <path/to/messages.jsonl>")
        print("\nExample:")
        print("  python format_messages.py results/cheat/experiment_name/messages.jsonl")
        sys.exit(1)
    
    jsonl_path = Path(sys.argv[1])
    
    if not jsonl_path.exists():
        print(f"Error: File not found: {jsonl_path}")
        sys.exit(1)
    
    if not jsonl_path.name.endswith('.jsonl'):
        print(f"Warning: Expected .jsonl file, got: {jsonl_path.name}")
    
    format_messages(jsonl_path)


if __name__ == "__main__":
    main()
