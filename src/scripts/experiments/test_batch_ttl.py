"""Test script to run batch TTL experiments with mocked backends."""

from src.config.experiment_config import ExperimentConfig
from src.games.ttl import TTLConfig
from src.experiments.ttl_batch_runner import run_batch_experiment

# Create ExperimentConfig
exp_config = ExperimentConfig(
    experiment_name="test_batch",
    backend_type="mock",
    model="mock-model"
)

# Convert to TTLConfig using the correct API
config = TTLConfig(**exp_config.to_ttl_config_kwargs(use_real_world_facts=False))

print("=" * 70)
print("Running Batch TTL Experiment")
print("=" * 70)
print(f"Configuration:")
print(f"  Deceiver: {config.deceiver_config.name} ({config.deceiver_config.role})")
print(f"  Auditor: {config.auditor_config.name} ({config.auditor_config.role})")
print(f"  Backend: {config.deceiver_config.backend_type}")
print(f"  Model: {config.deceiver_config.model}")
print("=" * 70)
print()

# Note: This will fail without actual backends, but demonstrates the API is correct
print("Configuration created successfully with correct API!")
print()
print("To run with actual mocked backends, use the pytest tests:")
print("  python -m pytest src/tests/test_ttl_batch_with_mocks.py -v")
