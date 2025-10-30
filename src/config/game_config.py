"""Base game configuration with git and config hash tracking."""

import hashlib
import json
import subprocess
from abc import ABC
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

from .player_config import PlayerConfig


@dataclass
class GameConfig(ABC):
    """Base configuration class for all games.
    
    Automatically computes git hash, config hash, and dirty flag for reproducibility.
    Subclasses should populate self.players in __post_init__ before calling super().__post_init__().
    
    Attributes:
        output_dir: Base directory for results
        players: List of player configurations (populated by subclasses)
        git_hash: Current git commit hash (auto-computed)
        config_hash: Hash of configuration (auto-computed)
        is_dirty: Whether repo has uncommitted changes (auto-computed)
    """
    
    output_dir: str = "./results"
    
    # Auto-computed fields (populated in __post_init__)
    players: List[PlayerConfig] = field(default_factory=list, init=False)
    git_hash: Optional[str] = field(default=None, init=False)
    config_hash: Optional[str] = field(default=None, init=False)
    is_dirty: bool = field(default=False, init=False)
    
    def __post_init__(self):
        """Compute git hash, dirty flag, and config hash.
        
        Subclasses should call super().__post_init__() AFTER populating self.players.
        """
        # Get git hash
        try:
            self.git_hash = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.git_hash = "nogit"
        
        # Check if repo is dirty
        try:
            subprocess.check_output(
                ["git", "diff", "--quiet"],
                stderr=subprocess.DEVNULL
            )
            subprocess.check_output(
                ["git", "diff", "--cached", "--quiet"],
                stderr=subprocess.DEVNULL
            )
            self.is_dirty = False
        except subprocess.CalledProcessError:
            self.is_dirty = True
        except FileNotFoundError:
            self.is_dirty = False
        
        # Compute config hash (exclude auto-computed fields)
        self.config_hash = self._compute_config_hash()
    
    def _compute_config_hash(self) -> str:
        """Compute hash of configuration.
        
        Excludes auto-computed fields (git_hash, config_hash, is_dirty).
        """
        config_dict = self.to_dict()
        
        # Remove auto-computed fields
        config_dict.pop("git_hash", None)
        config_dict.pop("config_hash", None)
        config_dict.pop("is_dirty", None)
        
        # Sort keys for deterministic hashing
        config_json = json.dumps(config_dict, sort_keys=True)
        return hashlib.sha256(config_json.encode()).hexdigest()[:7]
    
    def get_experiment_name(self, experiment_base: str) -> str:
        """Get full experiment name with git and config hashes.
        
        Format: {experiment_base}_{git_hash}_{config_hash}[_dirty]
        
        Args:
            experiment_base: Base name for the experiment
            
        Returns:
            Full experiment name with hashes
        """
        dirty_suffix = "_dirty" if self.is_dirty else ""
        return f"{experiment_base}_{self.git_hash}_{self.config_hash}{dirty_suffix}"
    
    def to_dict(self) -> dict:
        """Convert config to dictionary for serialization.
        
        Returns:
            Dictionary representation of config
        """
        result = {}
        for key, value in asdict(self).items():
            if key == "players":
                result[key] = [p.to_dict() if hasattr(p, "to_dict") else p for p in value]
            else:
                result[key] = value
        return result
    
    def save(self, filepath: Path):
        """Save configuration to JSON file.
        
        Args:
            filepath: Path to save configuration
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def from_file(cls, filepath: Path) -> "GameConfig":
        """Load configuration from JSON file.
        
        Note: This method removes auto-computed fields and reconstructs the config.
        Subclasses must ensure their __post_init__ correctly rebuilds the players list.
        
        Args:
            filepath: Path to configuration file
            
        Returns:
            Loaded configuration instance
        """
        with open(filepath) as f:
            config_dict = json.load(f)
        
        # Remove auto-computed fields (they'll be recomputed)
        config_dict.pop("git_hash", None)
        config_dict.pop("config_hash", None)
        config_dict.pop("is_dirty", None)
        config_dict.pop("players", None)  # Subclass will reconstruct
        
        # Note: Subclasses with nested dataclass fields (like player_template)
        # may need to override from_file() to properly reconstruct those fields
        return cls(**config_dict)
