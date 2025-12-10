"""Results logging for game experiments."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..backends.base import ProbeScores
from ..config.game_config import GameConfig


class ResultsLogger:
    """Logger for game experiment results.

    Creates directory structure: results/{game_name}/{experiment_name}/game{N}/
    Logs all player messages to JSONL files for easy parsing.

    Attributes:
        config: Game configuration
        game_name: Name of the game (werewolf, 3sat, ttl)
        experiment_name: Full experiment name with hashes
        game_id: Optional game instance ID for multiple runs
        results_dir: Full path to results directory
        messages_file: Path to messages JSONL file
    """

    def __init__(
        self,
        config: GameConfig,
        game_name: str,
        experiment_base: str,
        game_id: Optional[int] = None,
        auto_visualize: bool = True,
    ):
        """Initialize results logger.

        Args:
            config: Game configuration
            game_name: Name of the game (e.g., "werewolf", "3sat", "ttl")
            experiment_base: Base experiment name (e.g., "baseline", "high_temp")
            game_id: Optional game instance ID for multiple runs
            auto_visualize: If True, automatically generate visualizations when logging probe data
        """
        self.config = config
        self.game_name = game_name
        self.experiment_name = config.get_experiment_name(experiment_base)
        self.game_id = game_id
        self.auto_visualize = auto_visualize

        # Build directory path
        parts = [config.output_dir, game_name, self.experiment_name]
        if game_id is not None:
            parts.append(f"game{game_id}")

        self.results_dir = Path(*parts)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Setup log files
        self.messages_file = self.results_dir / "messages.jsonl"
        self.config_file = self.results_dir / "config.json"

        # Counter for visualization filenames
        self._viz_counter = 0

        # Accumulated visualization data for consolidated output
        self._viz_data = []

        # Save config on initialization
        self._save_config()

    def _save_config(self):
        """Save configuration to results directory."""
        self.config.save(self.config_file)

    def _generate_html_visualization(
        self,
        all_messages: List[Dict[str, Any]],
        title: str,
    ) -> str:
        """Generate consolidated HTML visualization of probe activations with multi-probe toggle.

        Args:
            all_messages: List of message data dicts with 'message_num', 'player_name', 'tokens', 'probe_scores'
            title: Title for the visualization

        Returns:
            HTML string with color-coded token visualization and interactive probe selector
        """
        import html
        import json

        if not all_messages:
            return ""

        # Collect all unique probe names
        probe_names = set()
        for msg in all_messages:
            if "probe_scores" in msg:
                probe_names.update(msg["probe_scores"].keys())
        probe_names = sorted(probe_names)

        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            '<meta charset="UTF-8">',
            f"<title>{html.escape(title)}</title>",
            "<style>",
            "body { font-family: monospace; padding: 20px; background: #f5f5f5; }",
            "h1 { color: #333; }",
            ".controls { margin: 20px 0; padding: 15px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            ".probe-selector { margin: 10px 0; }",
            ".probe-selector label { margin-right: 20px; cursor: pointer; }",
            '.probe-selector input[type="radio"] { margin-right: 5px; }',
            ".message-section { margin: 30px 0; padding: 20px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
            ".message-header { font-size: 16px; font-weight: bold; margin-bottom: 10px; color: #555; border-bottom: 2px solid #eee; padding-bottom: 5px; }",
            ".token-container { line-height: 1.8; margin-top: 10px; word-wrap: break-word; }",
            ".token { padding: 2px 1px; border-radius: 2px; position: relative; cursor: help; display: inline-block; }",
            ".token .tooltip { display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 5px; padding: 8px 12px; background: rgba(0, 0, 0, 0.9); color: white; border-radius: 4px; white-space: nowrap; font-size: 12px; z-index: 1000; pointer-events: none; }",
            '.token .tooltip::after { content: ""; position: absolute; top: 100%; left: 50%; transform: translateX(-50%); border: 5px solid transparent; border-top-color: rgba(0, 0, 0, 0.9); }',
            ".token:hover .tooltip { display: block; }",
            ".tooltip .probe-score { margin: 2px 0; }",
            ".tooltip .probe-score.selected { font-weight: bold; color: #ffff00; }",
            ".legend { margin: 20px 0; padding: 15px; background: #fafafa; border-radius: 5px; }",
            ".legend-item { display: inline-block; margin-right: 20px; }",
            ".legend-color { display: inline-block; width: 40px; height: 20px; border-radius: 3px; vertical-align: middle; margin-right: 5px; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>{html.escape(title)}</h1>",
            '<div class="legend">',
            "<strong>Color scale:</strong> ",
            '<span class="legend-item"><span class="legend-color" style="background: #00ff00;"></span>Low (0.0)</span>',
            '<span class="legend-item"><span class="legend-color" style="background: #ffff00;"></span>Medium (0.5)</span>',
            '<span class="legend-item"><span class="legend-color" style="background: #ff0000;"></span>High (1.0)</span>',
            "</div>",
            '<div class="controls">',
            '<div class="probe-selector">',
            "<strong>Select probe for coloring:</strong><br/>",
        ]

        # Add radio buttons for probe selection
        for i, probe_name in enumerate(probe_names):
            checked = " checked" if i == 0 else ""
            html_parts.append(
                f'<label><input type="radio" name="probe" value="{html.escape(probe_name)}"{checked}>'
                f"{html.escape(probe_name)}</label>"
            )

        html_parts.extend(
            [
                "</div>",  # probe-selector
                "</div>",  # controls
            ]
        )

        # Generate message sections with data attributes for JavaScript
        for msg_num, msg_data in enumerate(all_messages, 1):
            player_name = msg_data["player_name"]
            generation_tokens = msg_data.get("tokens", [])
            prompt_tokens = msg_data.get("prompt_tokens", [])
            probe_scores = msg_data.get("probe_scores", {})
            response = msg_data.get("response", "")

            # Combine prompt tokens + generation tokens for full sequence visualization
            all_tokens = prompt_tokens + generation_tokens

            html_parts.append(f'<div class="message-section" data-message="{msg_num}">')
            html_parts.append(
                f'<div class="message-header">Message #{msg_num} - {html.escape(player_name)}</div>'
            )
            html_parts.append('<div class="token-container">')

            # If tokens are available, show token-level visualization
            if all_tokens:
                # Create tokens with data attributes and tooltips for all probe scores
                for token_idx, token in enumerate(all_tokens):
                    # Build data attributes for all probes
                    data_attrs = []
                    tooltip_lines = []
                    for probe_name, probe_data in probe_scores.items():
                        # probe_data is a dict with 'aggregate_score', 'token_scores', and 'prompt_token_scores'
                        prompt_scores = (
                            probe_data.get("prompt_token_scores", [])
                            if isinstance(probe_data, dict)
                            else []
                        )
                        generation_scores = (
                            probe_data.get("token_scores", [])
                            if isinstance(probe_data, dict)
                            else probe_data
                        )

                        # Combine prompt + generation scores
                        combined_scores = prompt_scores + generation_scores

                        if token_idx < len(combined_scores):
                            score = combined_scores[token_idx]
                            data_attrs.append(
                                f'data-{html.escape(probe_name)}="{score:.6f}"'
                            )
                            tooltip_lines.append(
                                f'<div class="probe-score" data-probe="{html.escape(probe_name)}">{html.escape(probe_name)}: {score:.4f}</div>'
                            )

                    # Display token: replace 'Ġ' with space for readability
                    display_token = token.replace("Ġ", " ")
                    token_escaped = html.escape(display_token)

                    # Add original token in tooltip for debugging
                    original_token_line = f'<div style="border-top: 1px solid #555; margin-top: 4px; padding-top: 4px; font-size: 10px; color: #aaa;">Token: {html.escape(token)}</div>'
                    tooltip_html = (
                        f'<div class="tooltip">{"".join(tooltip_lines)}{original_token_line if token != display_token else ""}</div>'
                        if tooltip_lines
                        else ""
                    )

                    html_parts.append(
                        f'<span class="token" {" ".join(data_attrs)}>{token_escaped}{tooltip_html}</span>'
                    )
            else:
                # No tokens available - show plain text response
                html_parts.append(
                    f'<div style="color: #666; font-style: italic; padding: 10px;">{html.escape(response)}</div>'
                )

            html_parts.append("</div>")  # token-container
            html_parts.append("</div>")  # message-section

        # Add JavaScript for interactive probe switching
        html_parts.extend(
            [
                "<script>",
                "function calculateColor(score) {",
                "  score = Math.max(0.0, Math.min(1.0, score));",
                "  let r, g;",
                "  if (score < 0.5) {",
                "    r = Math.floor(255 * (score * 2));",
                "    g = 255;",
                "  } else {",
                "    r = 255;",
                "    g = Math.floor(255 * (2 - score * 2));",
                "  }",
                "  return `rgb(${r}, ${g}, 0)`;",
                "}",
                "",
                "function updateColors() {",
                "  const selectedProbe = document.querySelector('input[name=\"probe\"]:checked').value;",
                "  const tokens = document.querySelectorAll('.token');",
                "  ",
                "  tokens.forEach(token => {",
                "    const scoreAttr = token.getAttribute(`data-${selectedProbe}`);",
                "    if (scoreAttr !== null) {",
                "      const score = parseFloat(scoreAttr);",
                "      token.style.backgroundColor = calculateColor(score);",
                "      token.title = `${selectedProbe}: ${score.toFixed(4)}`;",
                "    } else {",
                '      token.style.backgroundColor = "#ccc";',
                "      token.title = `${selectedProbe}: N/A`;",
                "    }",
                "    ",
                "    // Update tooltip highlighting for selected probe",
                "    const probeScores = token.querySelectorAll('.probe-score');",
                "    probeScores.forEach(scoreDiv => {",
                "      if (scoreDiv.getAttribute('data-probe') === selectedProbe) {",
                "        scoreDiv.classList.add('selected');",
                "      } else {",
                "        scoreDiv.classList.remove('selected');",
                "      }",
                "    });",
                "  });",
                "}",
                "",
                "// Add event listeners to radio buttons",
                "document.querySelectorAll('input[name=\"probe\"]').forEach(radio => {",
                "  radio.addEventListener('change', updateColors);",
                "});",
                "",
                "// Initial color update",
                "updateColors();",
                "</script>",
                "</body>",
                "</html>",
            ]
        )

        return "\n".join(html_parts)

    def _generate_visualization(
        self,
        player_name: str,
        tokens: List[str],
        probe_scores: ProbeScores,
    ) -> None:
        """Accumulate visualization data for later consolidated generation.

        Args:
            player_name: Name of the player (for title/filename)
            tokens: List of generated tokens
            probe_scores: ProbeScores object with token-level data
        """
        if not self.auto_visualize:
            return

        if not tokens or not probe_scores or not probe_scores.scores:
            return

        try:
            # Increment counter
            self._viz_counter += 1

            # Extract token scores from ProbeScores object
            token_score_dict = {
                probe_name: score_data.token_scores
                for probe_name, score_data in probe_scores.scores.items()
            }

            # Accumulate data for consolidated visualization
            self._viz_data.append(
                {
                    "message_num": self._viz_counter,
                    "player_name": player_name,
                    "tokens": tokens,
                    "probe_scores": token_score_dict,
                }
            )
        except Exception as e:
            import traceback

            print(f"ERROR accumulating visualization data: {e}")
            traceback.print_exc()

    def log_message(
        self,
        player_name: str,
        role: str,
        prompt: str,
        response: str,
        tokens: Optional[List[str]] = None,
        prompt_tokens: Optional[List[str]] = None,
        top_k_logits: Optional[List[Dict[str, float]]] = None,
        probe_scores: Optional[ProbeScores] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log a player message with all metadata.

        Args:
            player_name: Name of the player
            role: Role in the message (user, assistant, system)
            prompt: Prompt sent to the player
            response: Response from the player
            tokens: Optional list of generated tokens
            prompt_tokens: Optional list of prompt tokens
            top_k_logits: Optional top-k logits for each token
            probe_scores: Optional probe scores
            metadata: Optional additional metadata
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "player_name": player_name,
            "role": role,
            "prompt": prompt,
            "response": response,
        }

        # Add optional fields if present
        if tokens is not None:
            entry["tokens"] = tokens

        if prompt_tokens is not None:
            entry["prompt_tokens"] = prompt_tokens

        if top_k_logits is not None:
            entry["top_k_logits"] = top_k_logits

        if probe_scores is not None:
            # Serialize ProbeScores with new nested structure
            # ProbeScores.scores is a dict mapping probe_name -> ProbeScoreData
            scores_dict = {}
            for probe_name, score_data in probe_scores.scores.items():
                scores_dict[probe_name] = {
                    "aggregate_score": score_data.aggregate_score,
                    "token_scores": score_data.token_scores,
                    "prompt_token_scores": score_data.prompt_token_scores,
                }
            entry["probe_scores"] = scores_dict

        if metadata is not None:
            entry["metadata"] = metadata

        # Generate visualization if enabled and data is available
        if self.auto_visualize and tokens and probe_scores:
            self._generate_visualization(player_name, tokens, probe_scores)

        # Append to JSONL file
        with open(self.messages_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def log_game_event(self, event_type: str, data: Dict[str, Any]):
        """Log a game event (e.g., round start, player elimination, game end).

        Args:
            event_type: Type of event (round_start, elimination, game_end, etc.)
            data: Event data
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "data": data,
        }

        events_file = self.results_dir / "events.jsonl"
        with open(events_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def save_results(self, results: Dict[str, Any]):
        """Save final game results to JSON file.

        Args:
            results: Dictionary of game results
        """
        results_file = self.results_dir / "results.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)

    def generate_consolidated_visualization(
        self, experiment_name: Optional[str] = None
    ) -> Optional[Path]:
        """Generate consolidated HTML visualization from accumulated data.

        Args:
            experiment_name: Optional name for the experiment (defaults to using experiment_name from config)

        Returns:
            Path to generated HTML file, or None if no data to visualize
        """
        if not self._viz_data:
            return None

        # Create visualizations directory
        viz_dir = self.results_dir / "visualizations"
        viz_dir.mkdir(parents=True, exist_ok=True)

        # Generate HTML title
        if experiment_name is None:
            experiment_name = self.experiment_name
        title = f"Probe Activations - {experiment_name}"

        # Generate consolidated HTML
        html_content = self._generate_html_visualization(
            all_messages=self._viz_data, title=title
        )

        if not html_content:
            return None

        # Save HTML file
        html_file = viz_dir / "consolidated_visualization.html"
        with open(html_file, "w") as f:
            f.write(html_content)

        return html_file

    def generate_readable_messages(self) -> Optional[Path]:
        """Generate human-readable markdown format of messages.jsonl.

        Automatically called at the end of a game to create a readable version
        of the messages log.

        Returns:
            Path to generated markdown file, or None if no messages exist
        """
        if not self.messages_file.exists():
            return None

        try:
            # Import the format function from the script
            import sys
            from pathlib import Path

            from .format_messages import format_messages

            # Generate the markdown file
            output_path = self.results_dir / "messages.md"
            format_messages(self.messages_file, output_path)

            return output_path

        except Exception as e:
            print(f"Warning: Could not generate readable messages: {e}")
            return None

    def get_results_path(self) -> Path:
        """Get path to results directory.

        Returns:
            Path to results directory
        """
        return self.results_dir
