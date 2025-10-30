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
    ):
        """Initialize results logger.
        
        Args:
            config: Game configuration
            game_name: Name of the game (e.g., "werewolf", "3sat", "ttl")
            experiment_base: Base experiment name (e.g., "baseline", "high_temp")
            game_id: Optional game instance ID for multiple runs
        """
        self.config = config
        self.game_name = game_name
        self.experiment_name = config.get_experiment_name(experiment_base)
        self.game_id = game_id
        
        # Build directory path
        parts = [config.output_dir, game_name, self.experiment_name]
        if game_id is not None:
            parts.append(f"game{game_id}")
        
        self.results_dir = Path(*parts)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup log files
        self.messages_file = self.results_dir / "messages.jsonl"
        self.config_file = self.results_dir / "config.json"
        
        # Save config on initialization
        self._save_config()
    
    def _save_config(self):
        """Save configuration to results directory."""
        self.config.save(self.config_file)
    
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
