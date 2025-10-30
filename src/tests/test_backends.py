"""Tests for backend implementations."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from ..backends.base import GenerationResult, ProbeScores
from ..backends.claude_backend import ClaudeBackend
from ..backends.openrouter_backend import OpenRouterBackend
from ..backends.modal_backend import ModalBackend
from ..backends import create_backend


class TestClaudeBackend:
    """Tests for ClaudeBackend."""
    
    def test_supports_probes(self):
        backend = ClaudeBackend()
        assert backend.supports_probes == False
    
    def test_supports_logits(self):
        backend = ClaudeBackend()
        assert backend.supports_logits == False
    
    @patch('subprocess.run')
    def test_generate_success(self, mock_run):
        """Test successful generation."""
        # Mock subprocess response
        mock_run.return_value = Mock(
            returncode=0,
            stdout="This is a test response."
        )
        
        backend = ClaudeBackend()
        result = backend.generate([
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello"}
        ])
        
        assert isinstance(result, GenerationResult)
        assert result.text == "This is a test response."
        assert result.tokens is None
        assert result.top_k_logits is None
        assert result.probe_scores is None
    
    @patch('subprocess.run')
    def test_generate_removes_warnings(self, mock_run):
        """Test that path warnings are filtered out."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="path was not found\nThis is the actual response."
        )
        
        backend = ClaudeBackend()
        result = backend.generate([{"role": "user", "content": "test"}])
        
        assert "was not found" not in result.text
        assert result.text == "This is the actual response."
    
    @patch('subprocess.run')
    def test_generate_failure(self, mock_run):
        """Test handling of subprocess failure."""
        mock_run.return_value = Mock(
            returncode=1,
            stderr="Command failed"
        )
        
        backend = ClaudeBackend()
        with pytest.raises(RuntimeError, match="Claude command failed"):
            backend.generate([{"role": "user", "content": "test"}])


class TestOpenRouterBackend:
    """Tests for OpenRouterBackend."""
    
    @patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'})
    def test_init_with_env_key(self):
        backend = OpenRouterBackend()
        assert backend.api_key == 'test_key'
    
    def test_init_with_explicit_key(self):
        backend = OpenRouterBackend(api_key='explicit_key')
        assert backend.api_key == 'explicit_key'
    
    @patch.dict('os.environ', {}, clear=True)
    def test_init_without_key_fails(self):
        with pytest.raises(ValueError, match="API key not found"):
            OpenRouterBackend()
    
    def test_supports_probes(self):
        backend = OpenRouterBackend(api_key='test')
        assert backend.supports_probes == False
    
    def test_supports_logits(self):
        backend = OpenRouterBackend(api_key='test')
        assert backend.supports_logits == False
    
    @patch('requests.post')
    def test_generate_success(self, mock_post):
        """Test successful generation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_post.return_value = mock_response
        
        backend = OpenRouterBackend(api_key='test')
        result = backend.generate([
            {"role": "user", "content": "Hello"}
        ])
        
        assert isinstance(result, GenerationResult)
        assert result.text == "Test response"
        assert result.tokens is None
        assert result.probe_scores is None
    
    @patch('requests.post')
    def test_generate_api_error(self, mock_post):
        """Test handling of API errors."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_post.return_value = mock_response
        
        backend = OpenRouterBackend(api_key='test')
        with pytest.raises(RuntimeError, match="OpenRouter API error"):
            backend.generate([{"role": "user", "content": "test"}])


class TestModalBackend:
    """Tests for ModalBackend."""
    
    def test_init_with_probe(self):
        backend = ModalBackend(probe="deception_8b")
        assert backend.probe_name == "deception_8b"
        assert backend.probe_config is not None
        assert backend.modal_app_name == "werewolf-apollo-probe"
    
    def test_init_without_probe_or_app_fails(self):
        with pytest.raises(ValueError, match="modal_app_name must be provided"):
            ModalBackend()
    
    def test_init_with_explicit_app_name(self):
        backend = ModalBackend(probe="deception_8b", modal_app_name="custom-app")
        assert backend.modal_app_name == "custom-app"
    
    def test_supports_probes_with_probe(self):
        backend = ModalBackend(probe="deception_8b")
        assert backend.supports_probes == True
    
    def test_supports_probes_without_probe(self):
        backend = ModalBackend(modal_app_name="test-app")
        assert backend.supports_probes == False
    
    def test_supports_logits(self):
        backend = ModalBackend(probe="deception_8b")
        assert backend.supports_logits == False


class TestBackendFactory:
    """Tests for create_backend factory function."""
    
    def test_create_claude(self):
        backend = create_backend("claude")
        assert isinstance(backend, ClaudeBackend)
    
    @patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test_key'})
    def test_create_openrouter(self):
        backend = create_backend("openrouter")
        assert isinstance(backend, OpenRouterBackend)
    
    def test_create_modal_with_probe(self):
        backend = create_backend("modal", probe="deception_8b")
        assert isinstance(backend, ModalBackend)
        assert backend.probe_name == "deception_8b"
    
    def test_create_unknown_backend(self):
        with pytest.raises(ValueError, match="Unknown backend type"):
            create_backend("unknown")


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""
    
    def test_minimal_result(self):
        result = GenerationResult(text="Hello")
        assert result.text == "Hello"
        assert result.tokens is None
        assert result.top_k_logits is None
        assert result.probe_scores is None
    
    def test_full_result(self):
        probe_scores = ProbeScores(
            aggregate_score=0.75,
            token_scores=[0.7, 0.8],
            metadata={"test": "value"}
        )
        result = GenerationResult(
            text="Hello",
            tokens=["Hello"],
            top_k_logits=[{"Hello": 0.9}],
            probe_scores=probe_scores
        )
        assert result.text == "Hello"
        assert result.tokens == ["Hello"]
        assert result.probe_scores.aggregate_score == 0.75


class TestProbeScores:
    """Tests for ProbeScores dataclass."""
    
    def test_minimal_scores(self):
        scores = ProbeScores(
            aggregate_score=0.5,
            token_scores=[0.4, 0.6]
        )
        assert scores.aggregate_score == 0.5
        assert scores.token_scores == [0.4, 0.6]
        assert scores.phase_scores is None
        assert scores.metadata == {}
    
    def test_full_scores(self):
        scores = ProbeScores(
            aggregate_score=0.5,
            token_scores=[0.4, 0.6],
            phase_scores={"prompt": 0.3, "action": 0.7},
            metadata={"num_tokens": 2}
        )
        assert scores.phase_scores["action"] == 0.7
        assert scores.metadata["num_tokens"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
