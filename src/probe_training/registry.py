"""Probe registry for managing trained probes."""

import json
import hashlib
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ProbeMetadata:
    """Metadata for a trained probe.
    
    Attributes:
        name: Probe name (e.g., "roleplaying-llama8b-linear-contrastive")
        dataset: Dataset name used for training
        model: Model name
        method: Training method name
        layer: Layer number
        checksum: SHA256 checksum of probe weights file
        created_at: ISO timestamp of creation
        hf_repo: HuggingFace repo where probe is stored (optional)
        metrics: Training metrics (loss, accuracy, etc.)
        git_tag: Git tag for this probe version (optional)
    """
    name: str
    dataset: str
    model: str
    method: str
    layer: int
    checksum: str
    created_at: str
    hf_repo: Optional[str] = None
    metrics: Optional[Dict] = None
    git_tag: Optional[str] = None


class ProbeRegistry:
    """Registry for managing trained probes.
    
    Handles:
    - Tracking probe metadata in probe_metadata.json
    - Downloading probes from HuggingFace
    - Caching probes locally in probes/ directory
    - Verifying probe integrity via checksums
    """
    
    def __init__(self, 
                 registry_file: Optional[Path] = None,
                 cache_dir: Optional[Path] = None):
        """Initialize probe registry.
        
        Args:
            registry_file: Path to probe_metadata.json (defaults to src/probe_training/probe_metadata.json)
            cache_dir: Path to local probe cache (defaults to probes/)
        """
        workspace_root = Path(__file__).parent.parent.parent
        self.registry_file = registry_file or (Path(__file__).parent / "probe_metadata.json")
        self.cache_dir = cache_dir or (workspace_root / "probes")
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load registry
        self._load_registry()
    
    def _load_registry(self):
        """Load probe metadata from registry file."""
        if not self.registry_file.exists():
            self.probes = {}
            return
        
        with open(self.registry_file, 'r') as f:
            data = json.load(f)
        
        self.probes = {
            name: ProbeMetadata(**metadata)
            for name, metadata in data.items()
        }
    
    def _save_registry(self):
        """Save probe metadata to registry file."""
        data = {
            name: asdict(metadata)
            for name, metadata in self.probes.items()
        }
        
        with open(self.registry_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def register_probe(self, metadata: ProbeMetadata):
        """Register a new probe in the registry.
        
        Args:
            metadata: Probe metadata
        """
        self.probes[metadata.name] = metadata
        self._save_registry()
    
    def get_probe_path(self, name: str) -> Path:
        """Get local path to probe, downloading if needed.
        
        Args:
            name: Probe name
            
        Returns:
            Path to probe weights file
            
        Raises:
            ValueError: If probe not found or corrupted
        """
        if name not in self.probes:
            raise ValueError(
                f"Probe not found in registry: {name}\n"
                f"Available probes: {list(self.probes.keys())}"
            )
        
        metadata = self.probes[name]
        probe_path = self.cache_dir / name / "probe.pt"
        
        # Check if probe exists in cache
        if probe_path.exists():
            # Verify integrity
            if self._verify_probe(probe_path, metadata.checksum):
                return probe_path
            else:
                print(f"Cached probe corrupted, re-downloading: {name}")
        
        # Download probe
        self._download_probe(metadata, probe_path)
        
        # Verify downloaded probe
        if not self._verify_probe(probe_path, metadata.checksum):
            raise ValueError(f"Downloaded probe is corrupted: {name}")
        
        return probe_path
    
    def _download_probe(self, metadata: ProbeMetadata, target_path: Path):
        """Download probe from HuggingFace.
        
        Args:
            metadata: Probe metadata
            target_path: Local path to save probe
        """
        if not metadata.hf_repo:
            raise ValueError(f"No HuggingFace repo specified for probe: {metadata.name}")
        
        # TODO: Implement HuggingFace download
        # For now, this is a stub
        raise NotImplementedError("HuggingFace download not yet implemented")
    
    def _verify_probe(self, probe_path: Path, expected_checksum: str) -> bool:
        """Verify probe integrity using checksum.
        
        Args:
            probe_path: Path to probe file
            expected_checksum: Expected SHA256 checksum
            
        Returns:
            True if checksum matches, False otherwise
        """
        actual_checksum = self._compute_checksum(probe_path)
        return actual_checksum == expected_checksum
    
    @staticmethod
    def _compute_checksum(file_path: Path) -> str:
        """Compute SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def list_probes(self) -> List[str]:
        """List all registered probes."""
        return list(self.probes.keys())
    
    def get_metadata(self, name: str) -> ProbeMetadata:
        """Get metadata for a probe.
        
        Args:
            name: Probe name
            
        Returns:
            Probe metadata
        """
        if name not in self.probes:
            raise ValueError(f"Probe not found: {name}")
        return self.probes[name]
