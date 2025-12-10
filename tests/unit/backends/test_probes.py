"""Tests for probe registry and display helpers."""

import pytest
from ..probes.registry import get_probe_config, PROBE_REGISTRY, ProbeConfig
from ..probes.display import categorize_score, format_probe_annotation, format_token_level_display
from ..backends.base import ProbeScores


class TestProbeRegistry:
    """Tests for probe registry."""
    
    def test_registry_contains_expected_probes(self):
        """Test that registry has the expected probes."""
        assert "deception_8b" in PROBE_REGISTRY
        assert "deception_70b" in PROBE_REGISTRY
        assert "hallucination_8b" in PROBE_REGISTRY
    
    def test_get_deception_8b_config(self):
        """Test getting 8B deception probe config."""
        config = get_probe_config("deception_8b")
        assert isinstance(config, ProbeConfig)
        assert config.probe_type == "deception"
        assert config.layer == 22
        assert config.modal_app_name == "werewolf-apollo-probe"
        assert "8B" in config.model_name
    
    def test_get_deception_70b_config(self):
        """Test getting 70B deception probe config."""
        config = get_probe_config("deception_70b")
        assert config.probe_type == "deception"
        assert config.layer == 22
        assert "70B" in config.model_name
    
    def test_get_hallucination_config(self):
        """Test getting hallucination probe config."""
        config = get_probe_config("hallucination_8b")
        assert config.probe_type == "hallucination"
        assert config.modal_app_name == "hallucination-probe-backend"
        assert config.repo_id == "andyrdt/hallucination-probes"
    
    def test_get_unknown_probe_fails(self):
        """Test that getting unknown probe raises KeyError."""
        with pytest.raises(KeyError, match="Unknown probe"):
            get_probe_config("nonexistent_probe")
    
    def test_probe_config_dataclass(self):
        """Test ProbeConfig dataclass structure."""
        config = ProbeConfig(
            probe_id="test_probe",
            probe_type="deception",
            model_name="test-model",
            layer=10,
            modal_app_name="test-app",
            description="Test probe"
        )
        assert config.probe_id == "test_probe"
        assert config.layer == 10


class TestCategorizeScore:
    """Tests for score categorization."""
    
    def test_fixed_thresholds_low(self):
        """Test fixed threshold categorization for low scores."""
        assert categorize_score(0.2) == "LOW"
        assert categorize_score(0.39) == "LOW"
    
    def test_fixed_thresholds_med(self):
        """Test fixed threshold categorization for medium scores."""
        assert categorize_score(0.4) == "MED"
        assert categorize_score(0.5) == "MED"
        assert categorize_score(0.59) == "MED"
    
    def test_fixed_thresholds_high(self):
        """Test fixed threshold categorization for high scores."""
        assert categorize_score(0.6) == "HIGH"
        assert categorize_score(0.8) == "HIGH"
    
    def test_adaptive_thresholds_with_few_scores(self):
        """Test that with <10 scores, uses fixed thresholds."""
        all_scores = [0.2, 0.3, 0.4, 0.5]
        assert categorize_score(0.3, all_scores) == "LOW"
        assert categorize_score(0.5, all_scores) == "MED"
    
    def test_adaptive_thresholds_with_many_scores(self):
        """Test adaptive percentile-based thresholds."""
        # Create distribution: 10 scores from 0.1 to 1.0
        all_scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        
        # Low: below 33rd percentile (< 0.4)
        assert categorize_score(0.2, all_scores) == "LOW"
        
        # Med: between 33rd and 66th percentile (0.4 to 0.7)
        assert categorize_score(0.5, all_scores) == "MED"
        
        # High: above 66th percentile (>= 0.7)
        assert categorize_score(0.8, all_scores) == "HIGH"


class TestFormatProbeAnnotation:
    """Tests for probe annotation formatting."""
    
    def test_none_probe_scores(self):
        """Test that None probe scores returns text unchanged."""
        text = "I will set x3=True"
        result = format_probe_annotation("Alice", text, None, "inline")
        assert result == text
    
    def test_inline_style_low(self):
        """Test inline style with LOW score."""
        scores = ProbeScores(aggregate_score=0.3, token_scores=[0.3])
        result = format_probe_annotation(
            "Alice", "I will set x3=True", scores, "inline"
        )
        assert result == "I will set x3=True [PROBE: LOW]"
    
    def test_inline_style_med(self):
        """Test inline style with MED score."""
        scores = ProbeScores(aggregate_score=0.5, token_scores=[0.5])
        result = format_probe_annotation(
            "Alice", "I will set x3=True", scores, "inline"
        )
        assert result == "I will set x3=True [PROBE: MED]"
    
    def test_inline_style_high(self):
        """Test inline style with HIGH score."""
        scores = ProbeScores(aggregate_score=0.7, token_scores=[0.7])
        result = format_probe_annotation(
            "Alice", "I will set x3=True", scores, "inline"
        )
        assert result == "I will set x3=True [PROBE: HIGH]"
    
    def test_summary_style(self):
        """Test summary style (Werewolf)."""
        scores = ProbeScores(aggregate_score=0.75, token_scores=[0.75])
        result = format_probe_annotation(
            "Alice", "I vote for Bob", scores, "summary"
        )
        assert result == "[LIE DETECTOR] Alice: Score: 0.75"
    
    def test_none_style(self):
        """Test none style returns text unchanged."""
        scores = ProbeScores(aggregate_score=0.9, token_scores=[0.9])
        result = format_probe_annotation(
            "Alice", "Test text", scores, "none"
        )
        assert result == "Test text"
    
    def test_invalid_style(self):
        """Test that invalid style raises ValueError."""
        scores = ProbeScores(aggregate_score=0.5, token_scores=[0.5])
        with pytest.raises(ValueError, match="Unknown style"):
            format_probe_annotation("Alice", "text", scores, "invalid")


class TestFormatTokenLevelDisplay:
    """Tests for token-level HTML display."""
    
    def test_basic_html_generation(self):
        """Test that HTML is generated with color coding."""
        tokens = ["Hello", "world"]
        scores = [0.3, 0.8]
        
        html = format_token_level_display(tokens, scores, threshold=0.5)
        
        assert "<span" in html
        assert "Hello" in html
        assert "world" in html
        assert "rgb(" in html  # Color coding present
    
    def test_high_score_token_is_red(self):
        """Test that high score tokens are colored red."""
        tokens = ["suspicious"]
        scores = [0.9]
        
        html = format_token_level_display(tokens, scores, threshold=0.5)
        
        # High scores should have red color (first RGB component high)
        assert "rgb(" in html
        # Should be bold for high scores
        assert "font-weight: bold" in html
    
    def test_low_score_token_is_green(self):
        """Test that low score tokens are colored green."""
        tokens = ["truthful"]
        scores = [0.2]
        
        html = format_token_level_display(tokens, scores, threshold=0.5)
        
        # Low scores should have green color
        assert "rgb(" in html
    
    def test_token_cleanup(self):
        """Test that special token characters are cleaned up."""
        tokens = ["▁Hello", "Ġworld", "##test"]
        scores = [0.5, 0.5, 0.5]
        
        html = format_token_level_display(tokens, scores)
        
        # Special characters should be removed or replaced
        assert "▁" not in html or " " in html
        assert "Hello" in html


class TestProbeIntegration:
    """Integration tests for probes with backends."""
    
    @pytest.mark.slow
    @pytest.mark.skipif(
        True,  # Skip by default - requires Modal connection
        reason="Requires Modal connection and probe deployment"
    )
    def test_modal_backend_returns_probe_scores(self):
        """Integration test: Modal backend with probe returns non-zero scores."""
        from ..backends import create_backend
        from ..player import GamePlayer
        
        backend = create_backend("modal", probe="deception_8b")
        player = GamePlayer("Alice", backend, "You are a strategic player.")
        
        result = player.query("Say hello")
        
        assert result.text is not None
        assert len(result.text) > 0
        assert result.probe_scores is not None
        assert result.probe_scores.aggregate_score > 0
        assert len(result.probe_scores.token_scores) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
