"""Dataset loading and integrity verification."""

import json
import hashlib
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass


@dataclass
class ContrastivePair:
    """A single contrastive pair for probe training.
    
    Attributes:
        positive: Truthful/honest statement
        negative: Deceptive/hallucinated statement
        metadata: Optional metadata about the pair
    """
    positive: str
    negative: str
    metadata: Optional[Dict] = None


class Dataset:
    """Dataset loader with integrity checking via checksums.
    
    Supports loading datasets from:
    - Local git-tracked datasets in datasets/ folder
    - External repos (e.g., external_repos/deception-detection/data/)
    - HuggingFace (optional, future support)
    """
    
    def __init__(self, dataset_name: str, dataset_root: Optional[Path] = None):
        """Initialize dataset loader.
        
        Args:
            dataset_name: Name of dataset (e.g., "roleplaying", "truthfulqa")
            dataset_root: Root directory for datasets (defaults to datasets/)
        """
        self.dataset_name = dataset_name
        self.dataset_root = dataset_root or Path(__file__).parent.parent.parent / "datasets"
        self.dataset_path = self.dataset_root / dataset_name
        
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Dataset not found: {self.dataset_path}\n"
                f"Available datasets: {self._list_available_datasets()}"
            )
    
    def load(self, split: str = "train") -> List[ContrastivePair]:
        """Load dataset split with integrity verification.
        
        Args:
            split: Dataset split ("train" or "val")
            
        Returns:
            List of contrastive pairs
            
        Raises:
            ValueError: If dataset is corrupted (checksum mismatch)
        """
        # Verify integrity first
        self._verify_integrity()
        
        # Load the split
        split_file = self.dataset_path / f"{split}.jsonl"
        if not split_file.exists():
            raise FileNotFoundError(f"Split not found: {split_file}")
        
        pairs = []
        with open(split_file, 'r') as f:
            for line in f:
                data = json.loads(line)
                pairs.append(ContrastivePair(
                    positive=data["positive"],
                    negative=data["negative"],
                    metadata=data.get("metadata")
                ))
        
        return pairs
    
    def _verify_integrity(self):
        """Verify dataset hasn't been corrupted using checksums.
        
        Raises:
            ValueError: If any file's checksum doesn't match expected
        """
        checksums_file = self.dataset_path / "checksums.json"
        
        if not checksums_file.exists():
            raise FileNotFoundError(
                f"No checksums.json found for dataset: {self.dataset_name}\n"
                f"Dataset integrity cannot be verified."
            )
        
        with open(checksums_file, 'r') as f:
            expected_checksums = json.load(f)
        
        for file_name, expected_checksum in expected_checksums.items():
            file_path = self.dataset_path / file_name
            if not file_path.exists():
                raise FileNotFoundError(f"Missing dataset file: {file_path}")
            
            actual_checksum = self._compute_checksum(file_path)
            if actual_checksum != expected_checksum:
                raise ValueError(
                    f"Corrupted dataset file: {file_name}\n"
                    f"Expected checksum: {expected_checksum}\n"
                    f"Actual checksum: {actual_checksum}\n"
                    f"Dataset: {self.dataset_name}"
                )
    
    @staticmethod
    def _compute_checksum(file_path: Path) -> str:
        """Compute SHA256 checksum of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hex string of SHA256 checksum
        """
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _list_available_datasets(self) -> List[str]:
        """List available datasets in dataset_root."""
        if not self.dataset_root.exists():
            return []
        return [d.name for d in self.dataset_root.iterdir() if d.is_dir()]
    
    @staticmethod
    def generate_checksums(dataset_path: Path) -> Dict[str, str]:
        """Generate checksums.json for a dataset directory.
        
        Useful for creating new datasets.
        
        Args:
            dataset_path: Path to dataset directory
            
        Returns:
            Dictionary of {filename: checksum}
        """
        checksums = {}
        for file_path in dataset_path.glob("*.jsonl"):
            checksums[file_path.name] = Dataset._compute_checksum(file_path)
        return checksums
