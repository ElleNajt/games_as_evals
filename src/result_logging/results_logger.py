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
        
        # Save config on initialization
        self._save_config()
    
    def _save_config(self):
        """Save configuration to results directory."""
        self.config.save(self.config_file)
    
    def _generate_html_visualization(
        self,
        tokens: List[str],
        probe_scores: Dict[str, List[float]],
        title: str,
    ) -> str:
        """Generate HTML visualization of probe activations.
        
        Args:
            tokens: List of generated tokens
            probe_scores: Dictionary mapping probe names to per-token scores
            title: Title for the visualization
            
        Returns:
            HTML string with color-coded token visualization
        """
        import html
        
        html_parts = [
            '<!DOCTYPE html>',
            '<html>',
            '<head>',
            '<meta charset="UTF-8">',
            f'<title>{html.escape(title)}</title>',
            '<style>',
            'body { font-family: monospace; padding: 20px; background: #f5f5f5; }',
            'h1 { color: #333; }',
            '.probe-section { margin: 30px 0; padding: 20px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }',
            '.probe-name { font-size: 18px; font-weight: bold; margin-bottom: 15px; color: #555; }',
            '.token-container { line-height: 2.5; }',
            '.token { padding: 4px 2px; border-radius: 3px; }',
            '.legend { margin: 20px 0; padding: 15px; background: #fafafa; border-radius: 5px; }',
            '.legend-item { display: inline-block; margin-right: 20px; }',
            '.legend-color { display: inline-block; width: 40px; height: 20px; border-radius: 3px; vertical-align: middle; margin-right: 5px; }',
            '</style>',
            '</head>',
            '<body>',
            f'<h1>{html.escape(title)}</h1>',
            '<div class="legend">',
            '<strong>Color scale:</strong> ',
            '<span class="legend-item"><span class="legend-color" style="background: #00ff00;"></span>Low (0.0)</span>',
            '<span class="legend-item"><span class="legend-color" style="background: #ffff00;"></span>Medium (0.5)</span>',
            '<span class="legend-item"><span class="legend-color" style="background: #ff0000;"></span>High (1.0)</span>',
            '</div>',
        ]
        
        # Generate visualization for each probe
        for probe_name, scores in probe_scores.items():
            html_parts.append('<div class="probe-section">')
            html_parts.append(f'<div class="probe-name">{html.escape(probe_name)}</div>')
            html_parts.append('<div class="token-container">')
            
            for token, score in zip(tokens, scores):
                # Clamp score to [0, 1]
                score = max(0.0, min(1.0, score))
                
                # Calculate RGB color (green -> yellow -> red)
                if score < 0.5:
                    # Green to yellow: increase red component
                    r = int(255 * (score * 2))
                    g = 255
                else:
                    # Yellow to red: decrease green component
                    r = 255
                    g = int(255 * (2 - score * 2))
                
                bg_color = f'rgb({r}, {g}, 0)'
                
                # Escape token for HTML
                token_escaped = html.escape(token)
                
                html_parts.append(
                    f'<span class="token" style="background-color: {bg_color};" '
                    f'title="{html.escape(probe_name)}: {score:.4f}">{token_escaped}</span>'
                )
            
            html_parts.append('</div>')  # token-container
            html_parts.append('</div>')  # probe-section
        
        html_parts.extend(['</body>', '</html>'])
        
        return '\n'.join(html_parts)
    
    def _generate_visualization(
        self,
        player_name: str,
        tokens: List[str],
        probe_scores: ProbeScores,
    ) -> None:
        """Generate and save HTML visualization for probe activations.
        
        Args:
            player_name: Name of the player (for title/filename)
            tokens: List of generated tokens
            probe_scores: ProbeScores object with token-level data
        """
        if not self.auto_visualize:
            return
        
        if not tokens or not probe_scores or not probe_scores.token_scores:
            return
        
        try:
            # Create visualization directory
            viz_dir = self.results_dir / "visualizations"
            viz_dir.mkdir(exist_ok=True)
            
            # Generate filename
            self._viz_counter += 1
            filename = f"{player_name}_{self._viz_counter:03d}_probe_activations.html"
            save_path = viz_dir / filename
            
            # Generate HTML visualization
            html_content = self._generate_html_visualization(
                tokens=tokens,
                probe_scores=probe_scores.token_scores,
                title=f"Probe Activations - {player_name} (Message {self._viz_counter})",
            )
            
            # Save to file
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
        except Exception:
            pass
    
    def log_message(
        self,
        player_name: str,
        role: str,
        prompt: str,
        response: str,
        tokens: Optional[List[str]] = None,
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
        
        if top_k_logits is not None:
            entry["top_k_logits"] = top_k_logits
        
        if probe_scores is not None:
            entry["probe_scores"] = {
                "aggregate_score": probe_scores.aggregate_score,
                "token_scores": probe_scores.token_scores,
                "phase_scores": probe_scores.phase_scores,
                "metadata": probe_scores.metadata,
            }
        
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
    
    def get_results_path(self) -> Path:
        """Get path to results directory.
        
        Returns:
            Path to results directory
        """
        return self.results_dir
