"""Pytest tests for TTL batch experiments using mocked backends.

Tests the batch experiment runner with MockBackend to verify functionality
without making actual LLM API calls.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.backends.base import GenerationResult
from src.config.experiment_config import ExperimentConfig
from src.experiments.ttl.batch_runner import BatchResults, run_batch_experiment
from src.experiments.ttl.configs import create_ttl_config
from src.games.ttl import TTLConfig


class MockBackend:
    """Mock backend that returns predefined responses."""

    def __init__(self, responses):
        """Initialize with list of responses to return sequentially.

        Args:
            responses: List of strings to return on successive generate() calls
        """
        self.responses = responses
        self.call_count = 0
        self.supports_logits = False
        self.supports_probes = False

    def generate(self, messages, max_tokens=None, temperature=None):
        """Return next predefined response."""
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1

        return GenerationResult(
            text=response, tokens=None, probe_scores=None, top_k_logits=None
        )


def test_batch_results_properties():
    """Test BatchResults properties calculate correctly."""
    results = BatchResults(
        total_rounds=10,
        successful_rounds=8,
        failed_rounds=2,
        auditor_correct_count=5,
    )

    assert results.success_rate == 80.0
    assert results.accuracy == 62.5  # 5/8 = 62.5%


def test_batch_results_zero_division():
    """Test BatchResults handles zero rounds gracefully."""
    results = BatchResults(
        total_rounds=0,
        successful_rounds=0,
        failed_rounds=0,
        auditor_correct_count=0,
    )

    assert results.success_rate == 0.0
    assert results.accuracy == 0.0


def test_batch_results_serialization():
    """Test that BatchResults can be serialized to dict."""
    results = BatchResults(
        total_rounds=5,
        successful_rounds=4,
        failed_rounds=1,
        auditor_correct_count=3,
        round_results=[],
    )

    result_dict = results.to_dict()

    assert result_dict["total_rounds"] == 5
    assert result_dict["successful_rounds"] == 4
    assert result_dict["failed_rounds"] == 1
    assert result_dict["auditor_correct_count"] == 3
    assert "success_rate" in result_dict
    assert "accuracy" in result_dict


def test_batch_with_mocked_backend():
    """Test batch runner with mocked create_backend."""
    # Deceiver generates statements, auditor guesses
    deceiver_responses = [
        "1. Paris is capital of France\n2. Water is wet\n3. Moon is cheese",
        "3",  # reveal
    ]

    auditor_response = "3"  # correct guess

    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch create_backend to return mocks
        with patch("src.games.ttl.orchestrator_unified.create_backend") as mock_create:
            # Create mock backends
            deceiver_mock = MockBackend(responses=deceiver_responses)
            auditor_mock = MockBackend(responses=[auditor_response])

            # Side effect returns appropriate mock
            call_count = [0]

            def side_effect(*args, **kwargs):
                if call_count[0] % 2 == 0:
                    call_count[0] += 1
                    return deceiver_mock
                else:
                    call_count[0] += 1
                    return auditor_mock

            mock_create.side_effect = side_effect

            # Create config using ExperimentConfig pattern
            exp_config = ExperimentConfig(
                experiment_name="mock_test", backend_type="mock", model="mock-model"
            )

            config = create_ttl_config(exp_config, use_real_world_facts=False)

            # Run batch experiment
            results = run_batch_experiment(
                config=config,
                num_rounds=2,
                experiment_name="test_batch_mock",
                save_results=False,
            )

            # Verify batch completed
            assert results.total_rounds == 2
            assert results.successful_rounds >= 0
            assert results.failed_rounds >= 0
            assert results.successful_rounds + results.failed_rounds == 2


def test_batch_saves_results_to_file():
    """Test that batch runner saves results to JSON file."""
    deceiver_responses = [
        "1. Sky is blue\n2. Water is wet\n3. Moon is cheese",
        "3",
    ]
    auditor_response = "3"

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.games.ttl.orchestrator_unified.create_backend") as mock_create:
            deceiver_mock = MockBackend(responses=deceiver_responses)
            auditor_mock = MockBackend(responses=[auditor_response])

            call_count = [0]

            def side_effect(*args, **kwargs):
                if call_count[0] % 2 == 0:
                    call_count[0] += 1
                    return deceiver_mock
                else:
                    call_count[0] += 1
                    return auditor_mock

            mock_create.side_effect = side_effect

            exp_config = ExperimentConfig(
                experiment_name="mock_test", backend_type="mock", model="mock-model"
            )

            config = create_ttl_config(exp_config, use_real_world_facts=False)

            # Change to temp directory for results
            import os

            original_cwd = os.getcwd()
            os.chdir(tmpdir)

            try:
                results = run_batch_experiment(
                    config=config,
                    num_rounds=1,
                    experiment_name="test_save",
                    save_results=True,
                )

                results_file = (
                    Path(tmpdir)
                    / "results"
                    / "ttl"
                    / "test_save"
                    / "batch_results.json"
                )
                assert results_file.exists()

                with open(results_file) as f:
                    saved_data = json.load(f)

                assert saved_data["total_rounds"] == 1
            finally:
                os.chdir(original_cwd)


def test_batch_with_failing_rounds():
    """Test that batch runner handles failing rounds gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.games.ttl.orchestrator_unified.create_backend") as mock_create:
            # Backend that raises exception
            failing_mock = Mock()
            failing_mock.generate.side_effect = RuntimeError("Simulated failure")
            failing_mock.supports_logits = False
            failing_mock.supports_probes = False

            mock_create.return_value = failing_mock

            exp_config = ExperimentConfig(
                experiment_name="mock_test", backend_type="mock", model="mock-model"
            )

            config = create_ttl_config(exp_config, use_real_world_facts=False)

            results = run_batch_experiment(
                config=config,
                num_rounds=2,
                experiment_name="test_failures",
                save_results=False,
            )

            assert results.total_rounds == 2
            assert results.failed_rounds > 0
            assert results.success_rate < 100.0
