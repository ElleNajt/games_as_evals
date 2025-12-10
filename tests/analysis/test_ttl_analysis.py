"""Tests for TTL analysis scripts."""

import json
import pytest
from pathlib import Path
from src.analysis.ttl.analyze_probe import load_experiment_data, analyze_probe_performance
from src.analysis.ttl.analyze_lie_patterns import analyze_lie_patterns
from src.analysis.ttl.analyze_lie_characteristics import analyze_lie_characteristics


@pytest.fixture
def mock_ttl_experiment(tmp_path):
    """Create a mock TTL experiment directory structure."""
    experiment_dir = tmp_path / "ttl_test_experiment"
    experiment_dir.mkdir()
    
    # Create batch_results.json
    batch_results = {
        "total_rounds": 3,
        "successful_rounds": 3,
        "failed_rounds": 0,
        "auditor_correct_count": 1,
        "success_rate": 100.0,
        "accuracy": 33.3,
    }
    with open(experiment_dir / "batch_results.json", "w") as f:
        json.dump(batch_results, f)
    
    # Create 3 game directories with results
    for game_id in range(1, 4):
        game_dir = experiment_dir / f"game{game_id}"
        game_dir.mkdir()
        
        # Mock game results
        game_result = {
            "success": True,
            "revealed_lie": game_id,  # Lie at position 1, 2, 3 respectively
            "deceiver_generation": {
                "statements": [
                    "Statement one is a truth about history.",
                    "Statement two is another historical fact.",
                    "Statement three contains a false claim."
                ],
                "avg_scores": {
                    "1": 0.75 if game_id == 1 else 0.65,
                    "2": 0.70 if game_id == 2 else 0.60,
                    "3": 0.80 if game_id == 3 else 0.55,
                }
            },
            "auditor_guesses": {
                "with_probe": {
                    "original_guess": int(max(
                        [(k, v) for k, v in {
                            "1": 0.75 if game_id == 1 else 0.65,
                            "2": 0.70 if game_id == 2 else 0.60,
                            "3": 0.80 if game_id == 3 else 0.55,
                        }.items()
                    ], key=lambda x: x[1])[0])
                },
                "without_probe": {
                    "original_guess": 2  # Always guesses position 2
                }
            },
            "auditor_correct_with_probe": (game_id == 3),  # Only correct on game 3
            "auditor_correct_without_probe": (game_id == 2),  # Only correct on game 2
        }
        
        with open(game_dir / "game_results.json", "w") as f:
            json.dump(game_result, f)
    
    return experiment_dir


def test_load_experiment_data(mock_ttl_experiment):
    """Test loading experiment data."""
    data = load_experiment_data(mock_ttl_experiment)
    
    assert "batch" in data
    assert "games" in data
    assert data["batch"]["total_rounds"] == 3
    assert len(data["games"]) == 3


def test_analyze_probe_performance(mock_ttl_experiment, capsys):
    """Test probe performance analysis."""
    data = load_experiment_data(mock_ttl_experiment)
    analyze_probe_performance(data)
    
    captured = capsys.readouterr()
    
    # Check that output contains expected sections
    assert "PROBE PERFORMANCE ANALYSIS" in captured.out
    assert "Round-by-round analysis:" in captured.out
    assert "SUMMARY STATISTICS" in captured.out
    assert "Raw probe accuracy" in captured.out
    assert "Auditor WITH probe accuracy" in captured.out
    assert "Auditor WITHOUT probe accuracy" in captured.out


def test_analyze_lie_patterns(mock_ttl_experiment, capsys):
    """Test lie pattern analysis."""
    data = load_experiment_data(mock_ttl_experiment)
    analyze_lie_patterns(data)
    
    captured = capsys.readouterr()
    
    # Check output contains expected sections
    assert "LIE PATTERN ANALYSIS" in captured.out
    assert "Auditor WITHOUT probe guess distribution:" in captured.out
    assert "Actual lie distribution:" in captured.out
    assert "Sample of lies vs truths:" in captured.out


def test_analyze_lie_characteristics(mock_ttl_experiment, capsys):
    """Test lie characteristics analysis."""
    data = load_experiment_data(mock_ttl_experiment)
    analyze_lie_characteristics(data)
    
    captured = capsys.readouterr()
    
    # Check output contains expected sections
    assert "LIE vs TRUTH CHARACTERISTICS" in captured.out
    assert "Statement lengths:" in captured.out
    assert "Average lie length:" in captured.out
    assert "Average truth length:" in captured.out
    assert "Sample lies to look for patterns:" in captured.out


def test_probe_accuracy_calculation(mock_ttl_experiment):
    """Test that probe accuracy is calculated correctly."""
    data = load_experiment_data(mock_ttl_experiment)
    games = data["games"]
    
    # Count how many times probe is correct (highest score = lie)
    probe_correct = 0
    for game in games:
        lie_pos = game["revealed_lie"]
        avg_scores = game["deceiver_generation"]["avg_scores"]
        highest_score_pos = int(max(avg_scores.items(), key=lambda x: x[1])[0])
        
        if highest_score_pos == lie_pos:
            probe_correct += 1
    
    # In our mock data, all 3 games should have probe correct
    # (game 1: pos 1 has 0.75, game 2: pos 2 has 0.70, game 3: pos 3 has 0.80)
    assert probe_correct == 3


def test_auditor_following_probe(mock_ttl_experiment):
    """Test detection of auditor following probe."""
    data = load_experiment_data(mock_ttl_experiment)
    games = data["games"]
    
    # Count how many times auditor with probe followed the probe
    followed_probe = 0
    for game in games:
        avg_scores = game["deceiver_generation"]["avg_scores"]
        highest_score_pos = int(max(avg_scores.items(), key=lambda x: x[1])[0])
        with_probe_guess = game["auditor_guesses"]["with_probe"]["original_guess"]
        
        if with_probe_guess == highest_score_pos:
            followed_probe += 1
    
    # All auditors should follow probe in our mock
    assert followed_probe == 3
