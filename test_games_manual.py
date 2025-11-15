#!/usr/bin/env python3
"""Manual test for games with mocked backends (no pytest required)."""

import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from src.backends.base import GenerationResult, ProbeScores, ProbeScoreData
from src.player import GamePlayer
from src.result_logging import ResultsLogger
from src.config import GameConfig


class MockBackend:
    """Mock backend that returns predefined responses."""
    
    def __init__(
        self,
        responses: Optional[List[str]] = None,
        with_probes: bool = False,
        with_logits: bool = False
    ):
        self.responses = responses or ["Mock response."]
        self.call_count = 0
        self._with_probes = with_probes
        self._with_logits = with_logits
    
    @property
    def supports_probes(self) -> bool:
        return self._with_probes
    
    @property
    def supports_logits(self) -> bool:
        return self._with_logits
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """Return mock response."""
        response_text = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        
        tokens = response_text.split() if self._with_probes or self._with_logits else None
        
        probe_scores = None
        if self._with_probes:
            probe_scores = ProbeScores(
                scores={
                    "deception_8b": ProbeScoreData(
                        aggregate_score=0.5,
                        token_scores=[0.5] * len(tokens),
                        metadata={"num_tokens": len(tokens), "probe_type": "deception"}
                    )
                }
            )
        
        top_k_logits = None
        if self._with_logits and tokens:
            top_k_logits = [
                {token: -1.0, "alt1": -2.0, "alt2": -3.0}
                for token in tokens
            ]
        
        return GenerationResult(
            text=response_text,
            tokens=tokens,
            top_k_logits=top_k_logits,
            probe_scores=probe_scores
        )


def test_game_player_basic():
    """Test GamePlayer with basic mock backend."""
    print("Test: GamePlayer with basic mock backend...")
    
    mock_backend = MockBackend(responses=["Hello, world!"])
    player = GamePlayer(
        name="Alice",
        backend=mock_backend,
        system_prompt="You are Alice."
    )
    
    result = player.query("How are you?")
    
    assert result.text == "Hello, world!"
    assert mock_backend.call_count == 1
    print("✓ PASS: Basic GamePlayer works")


def test_game_player_with_probes():
    """Test GamePlayer with probe-enabled backend."""
    print("\nTest: GamePlayer with probes...")
    
    mock_backend = MockBackend(
        responses=["I'm doing great!"],
        with_probes=True
    )
    
    player = GamePlayer(
        name="Bob",
        backend=mock_backend,
        system_prompt="You are Bob."
    )
    
    result = player.query("What's your strategy?")
    
    assert result.text == "I'm doing great!"
    assert result.tokens is not None
    assert result.probe_scores is not None
    assert "deception_8b" in result.probe_scores
    assert result.probe_scores["deception_8b"].aggregate_score == 0.5
    print("✓ PASS: Probes work correctly")


def test_game_player_with_logits():
    """Test GamePlayer with logits-enabled backend."""
    print("\nTest: GamePlayer with logits...")
    
    mock_backend = MockBackend(
        responses=["Strategic move here."],
        with_logits=True
    )
    
    player = GamePlayer(
        name="Charlie",
        backend=mock_backend,
        system_prompt="You are Charlie."
    )
    
    result = player.query("What do you think?")
    
    assert result.text == "Strategic move here."
    assert result.tokens is not None
    assert result.top_k_logits is not None
    assert len(result.top_k_logits) == len(result.tokens)
    print("✓ PASS: Logits work correctly")


def test_game_player_multiple_queries():
    """Test GamePlayer handles multiple queries."""
    print("\nTest: Multiple queries...")
    
    responses = [
        "First response.",
        "Second response.",
        "Third response."
    ]
    
    mock_backend = MockBackend(responses=responses)
    player = GamePlayer("Dave", mock_backend)
    
    result1 = player.query("Query 1")
    result2 = player.query("Query 2")
    result3 = player.query("Query 3")
    
    assert result1.text == "First response."
    assert result2.text == "Second response."
    assert result3.text == "Third response."
    assert mock_backend.call_count == 3
    print("✓ PASS: Multiple queries work")


def test_game_player_with_logging():
    """Test GamePlayer logs messages correctly."""
    print("\nTest: GamePlayer with logging...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config = GameConfig(output_dir=tmpdir)
        logger = ResultsLogger(config, "test_game", "mock_experiment")
        
        mock_backend = MockBackend(
            responses=["Logged response."],
            with_probes=True,
            with_logits=True
        )
        
        player = GamePlayer(
            name="Eve",
            backend=mock_backend,
            system_prompt="You are Eve.",
            logger=logger
        )
        
        result = player.query("Test query")
        
        # Verify result
        assert result.text == "Logged response."
        
        # Verify log file exists
        messages_log = Path(logger.results_dir) / "messages.jsonl"
        assert messages_log.exists()
        
        # Read log and verify content
        import json
        with open(messages_log) as f:
            lines = f.readlines()
            assert len(lines) > 0
            
            log_entry = json.loads(lines[0])
            assert log_entry["player_name"] == "Eve"
            assert log_entry["response"] == "Logged response."
            assert "tokens" in log_entry
            assert "probe_scores" in log_entry
            assert "top_k_logits" in log_entry
        
        print("✓ PASS: Logging works correctly")


def test_mock_backend_cycles_responses():
    """Test MockBackend cycles through responses."""
    print("\nTest: MockBackend response cycling...")
    
    responses = ["First", "Second", "Third"]
    backend = MockBackend(responses=responses)
    
    # Call more times than responses available
    for i in range(6):
        result = backend.generate(messages=[])
        expected = responses[i % len(responses)]
        assert result.text == expected
    
    print("✓ PASS: Response cycling works")


def test_mock_backend_capabilities():
    """Test MockBackend reports capabilities correctly."""
    print("\nTest: MockBackend capabilities...")
    
    basic = MockBackend()
    assert not basic.supports_probes
    assert not basic.supports_logits
    
    with_probes = MockBackend(with_probes=True)
    assert with_probes.supports_probes
    assert not with_probes.supports_logits
    
    with_logits = MockBackend(with_logits=True)
    assert not with_logits.supports_probes
    assert with_logits.supports_logits
    
    full_featured = MockBackend(with_probes=True, with_logits=True)
    assert full_featured.supports_probes
    assert full_featured.supports_logits
    
    print("✓ PASS: Capability flags work correctly")


if __name__ == "__main__":
    print("=" * 70)
    print("Running mock-based game tests")
    print("=" * 70)
    
    try:
        test_game_player_basic()
        test_game_player_with_probes()
        test_game_player_with_logits()
        test_game_player_multiple_queries()
        test_game_player_with_logging()
        test_mock_backend_cycles_responses()
        test_mock_backend_capabilities()
        
        print("\n" + "=" * 70)
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("=" * 70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
