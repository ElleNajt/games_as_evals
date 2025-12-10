"""Unit tests for probe training infrastructure.

Tests cover components that don't require heavy dependencies (torch, transformers).
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from dataclasses import asdict

from src.probe_training.config import TrainingConfig
from src.probe_training.dataset import Dataset, ContrastivePair
from src.probe_training.registry import ProbeRegistry, ProbeMetadata


class TestTrainingConfig:
    """Test TrainingConfig dataclass and methods."""

    def test_config_creation(self):
        """Test basic config creation."""
        config = TrainingConfig(
            dataset_name="roleplaying",
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            method="massmean",
            layer=12
        )
        assert config.dataset_name == "roleplaying"
        assert config.model == "meta-llama/Meta-Llama-3.1-8B-Instruct"
        assert config.method == "massmean"
        assert config.layer == 12

    def test_probe_naming_8b(self):
        """Test probe naming for 8B model."""
        config = TrainingConfig(
            dataset_name="roleplaying",
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            method="massmean",
            layer=12
        )
        name = config.generate_probe_name()
        assert name == "roleplaying-llama8b-massmean"

    def test_probe_naming_70b(self):
        """Test probe naming for 70B model."""
        config = TrainingConfig(
            dataset_name="truthfulqa",
            model="meta-llama/Llama-3.3-70B-Instruct",
            method="ccs",
            layer=22
        )
        name = config.generate_probe_name()
        assert name == "truthfulqa-llama70b-ccs"

    def test_default_values(self):
        """Test default hyperparameters."""
        config = TrainingConfig(
            dataset_name="test",
            model="test-model",
            method="massmean",
            layer=0
        )
        assert config.learning_rate == 1e-3
        assert config.num_epochs == 10
        assert config.batch_size == 8
        assert config.seed == 42
        assert config.device == "cuda"


class TestDataset:
    """Test Dataset loading and validation."""

    def test_dataset_loading(self):
        """Test loading roleplaying dataset."""
        dataset = Dataset("roleplaying")
        train_data = dataset.load("train")
        val_data = dataset.load("val")

        assert len(train_data) == 296
        assert len(val_data) == 75
        assert isinstance(train_data[0], ContrastivePair)

    def test_contrastive_pair_format(self):
        """Test ContrastivePair dataclass structure."""
        dataset = Dataset("roleplaying")
        train_data = dataset.load("train")

        pair = train_data[0]
        assert hasattr(pair, "positive")
        assert hasattr(pair, "negative")
        assert isinstance(pair.positive, str)
        assert isinstance(pair.negative, str)
        assert len(pair.positive) > 0
        assert len(pair.negative) > 0

    def test_checksum_verification(self):
        """Test that checksums exist and are valid."""
        dataset = Dataset("roleplaying")
        checksums_path = dataset.dataset_path / "checksums.json"

        assert checksums_path.exists()

        with open(checksums_path, 'r') as f:
            checksums = json.load(f)

        assert "train.jsonl" in checksums
        assert "val.jsonl" in checksums
        assert len(checksums["train.jsonl"]) == 64  # SHA256 length
        assert len(checksums["val.jsonl"]) == 64

    def test_invalid_split(self):
        """Test that invalid split raises error."""
        dataset = Dataset("roleplaying")

        with pytest.raises(ValueError):
            dataset.load("invalid_split")

    def test_invalid_dataset(self):
        """Test that nonexistent dataset raises error."""
        with pytest.raises(FileNotFoundError):
            dataset = Dataset("nonexistent_dataset")
            dataset.load("train")


class TestProbeMetadata:
    """Test ProbeMetadata dataclass."""

    def test_metadata_creation(self):
        """Test creating probe metadata."""
        metadata = ProbeMetadata(
            name="roleplaying-llama8b-massmean",
            dataset="roleplaying",
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            method="massmean",
            layer=12,
            checksum="abc123",
            created_at="2025-01-01T00:00:00",
            metrics={"accuracy": 0.77}
        )

        assert metadata.name == "roleplaying-llama8b-massmean"
        assert metadata.layer == 12
        assert metadata.metrics["accuracy"] == 0.77
        assert metadata.hf_repo is None
        assert metadata.modal_path is None

    def test_metadata_serialization(self):
        """Test metadata JSON serialization."""
        metadata = ProbeMetadata(
            name="test-probe",
            dataset="test",
            model="test-model",
            method="massmean",
            layer=0,
            checksum="abc",
            created_at="2025-01-01",
            metrics={"accuracy": 0.5}
        )

        # Should be serializable to dict
        metadata_dict = asdict(metadata)
        assert isinstance(metadata_dict, dict)
        assert metadata_dict["name"] == "test-probe"

        # Should be JSON-serializable
        json_str = json.dumps(metadata_dict)
        assert isinstance(json_str, str)

        # Should be deserializable
        loaded_dict = json.loads(json_str)
        loaded_metadata = ProbeMetadata(**loaded_dict)
        assert loaded_metadata.name == metadata.name


class TestProbeRegistry:
    """Test ProbeRegistry functionality."""

    def setup_method(self):
        """Create temporary directory for registry tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.registry_file = Path(self.temp_dir) / "test_registry.json"
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.cache_dir.mkdir()

    def teardown_method(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = ProbeRegistry(
            registry_file=self.registry_file,
            cache_dir=self.cache_dir
        )

        assert registry.registry_file == self.registry_file
        assert registry.cache_dir == self.cache_dir
        assert len(registry.list_probes()) == 0

    def test_probe_registration(self):
        """Test registering a probe."""
        registry = ProbeRegistry(
            registry_file=self.registry_file,
            cache_dir=self.cache_dir
        )

        metadata = ProbeMetadata(
            name="test-probe",
            dataset="test",
            model="test-model",
            method="massmean",
            layer=0,
            checksum="abc123",
            created_at="2025-01-01",
            metrics={"accuracy": 0.5}
        )

        registry.register_probe(metadata)

        # Verify probe is registered
        probes = registry.list_probes()
        assert len(probes) == 1
        assert "test-probe" in probes

        # Verify metadata can be retrieved
        retrieved = registry.get_metadata("test-probe")
        assert retrieved.name == "test-probe"
        assert retrieved.metrics["accuracy"] == 0.5

    def test_registry_persistence(self):
        """Test that registry persists to disk."""
        metadata = ProbeMetadata(
            name="persistent-probe",
            dataset="test",
            model="test-model",
            method="massmean",
            layer=0,
            checksum="xyz789",
            created_at="2025-01-01"
        )

        # Register probe
        registry1 = ProbeRegistry(
            registry_file=self.registry_file,
            cache_dir=self.cache_dir
        )
        registry1.register_probe(metadata)

        # Create new registry instance (simulates restart)
        registry2 = ProbeRegistry(
            registry_file=self.registry_file,
            cache_dir=self.cache_dir
        )

        # Verify probe still exists
        probes = registry2.list_probes()
        assert len(probes) == 1
        assert "persistent-probe" in probes

    def test_get_nonexistent_probe(self):
        """Test retrieving nonexistent probe raises error."""
        registry = ProbeRegistry(
            registry_file=self.registry_file,
            cache_dir=self.cache_dir
        )

        with pytest.raises(ValueError, match="Probe not found"):
            registry.get_metadata("nonexistent-probe")

    def test_multiple_probes(self):
        """Test registering multiple probes."""
        registry = ProbeRegistry(
            registry_file=self.registry_file,
            cache_dir=self.cache_dir
        )

        # Register multiple probes
        for i in range(3):
            metadata = ProbeMetadata(
                name=f"probe-{i}",
                dataset="test",
                model="test-model",
                method="massmean",
                layer=i,
                checksum=f"checksum-{i}",
                created_at="2025-01-01"
            )
            registry.register_probe(metadata)

        # Verify all probes are registered
        probes = registry.list_probes()
        assert len(probes) == 3
        assert "probe-0" in probes
        assert "probe-1" in probes
        assert "probe-2" in probes


class TestChecksumComputation:
    """Test checksum utilities."""

    def test_checksum_generation(self):
        """Test generating checksums for dataset files."""
        # Test with actual roleplaying dataset
        dataset = Dataset("roleplaying")

        # Compute checksums
        train_file = dataset.dataset_path / "train.jsonl"
        computed_checksum = ProbeRegistry._compute_checksum(train_file)

        # Load expected checksums
        with open(dataset.dataset_path / "checksums.json", 'r') as f:
            expected_checksums = json.load(f)

        # Verify checksum matches
        assert computed_checksum == expected_checksums["train.jsonl"]

    def test_checksum_format(self):
        """Test that checksums are valid SHA256 hashes."""
        dataset = Dataset("roleplaying")
        train_file = dataset.dataset_path / "train.jsonl"
        checksum = ProbeRegistry._compute_checksum(train_file)

        # SHA256 checksums are 64 hex characters
        assert len(checksum) == 64
        assert all(c in "0123456789abcdef" for c in checksum)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
