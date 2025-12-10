"""Unit tests for configuration layer.

Tests configuration transformations without making expensive Modal API calls.
Validates:
- PlayerConfig multi-probe support and backward compatibility
- ExperimentConfig.to_player_config_kwargs() correctness
- ExperimentConfig.to_ttl_config_kwargs() creates TTLPlayerConfig with role
- Parameter filtering (no extra params passed to configs)

Run with: python src/tests/test_config_layer.py
"""

import sys
sys.path.insert(0, '/workspace')

from src.config.player_config import PlayerConfig
from src.config.experiment_config import ExperimentConfig
from src.experiments.werewolf.configs import create_werewolf_config
from src.experiments.ttl.configs import create_ttl_config
from src.games.ttl.config import TTLPlayerConfig, TTLConfig


def test_single_probe_backward_compatibility():
    """Test that single probe parameter still works."""
    config = PlayerConfig(
        name="test_player",
        backend_type="modal",
        model="test_model",
        probe="deception_70b"
    )
    
    assert config.probe == "deception_70b"
    assert config.probes == ["deception_70b"], f"Expected ['deception_70b'], got {config.probes}"
    print("✓ Single probe backward compatibility")


def test_multiple_probes():
    """Test that multiple probes can be specified."""
    config = PlayerConfig(
        name="test_player",
        backend_type="modal",
        model="test_model",
        probes=["deception_70b", "hallucination_70b"]
    )
    
    assert config.probe is None
    assert config.probes == ["deception_70b", "hallucination_70b"]
    print("✓ Multiple probes support")


def test_no_probes():
    """Test that probes are optional."""
    config = PlayerConfig(
        name="test_player",
        backend_type="modal",
        model="test_model"
    )
    
    assert config.probe is None
    assert config.probes is None
    print("✓ No probes (optional)")


def test_both_probe_and_probes_raises_error():
    """Test that specifying both probe and probes raises ValueError."""
    try:
        PlayerConfig(
            name="test_player",
            backend_type="modal",
            model="test_model",
            probe="deception_70b",
            probes=["hallucination_70b"]
        )
        raise AssertionError("Expected ValueError to be raised")
    except ValueError as e:
        assert "Cannot specify both 'probe' and 'probes'" in str(e)
    print("✓ Both probe and probes raises ValueError")


def test_to_dict_includes_probes():
    """Test that to_dict() includes probes field."""
    config = PlayerConfig(
        name="test_player",
        backend_type="modal",
        model="test_model",
        probes=["deception_70b", "hallucination_70b"]
    )
    
    config_dict = config.to_dict()
    assert "probes" in config_dict
    assert config_dict["probes"] == ["deception_70b", "hallucination_70b"]
    print("✓ to_dict() includes probes")


def test_basic_kwargs_no_probes():
    """Test kwargs without probes."""
    exp_config = ExperimentConfig(
        backend_type="modal",
        model="meta-llama/Llama-3.3-70B-Instruct",
        temperature=0.7,
        max_tokens=512
    )
    
    kwargs = exp_config.to_player_config_kwargs("TestPlayer", "Test prompt")
    
    assert kwargs["name"] == "TestPlayer"
    assert kwargs["backend_type"] == "modal"
    assert kwargs["model"] == "meta-llama/Llama-3.3-70B-Instruct"
    assert kwargs["system_prompt"] == "Test prompt"
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] == 512
    assert "probe" not in kwargs
    assert "probes" not in kwargs
    print("✓ Basic kwargs (no probes)")


def test_single_probe_creates_probe_kwarg():
    """Test that single probe creates 'probe' kwarg (backward compatible)."""
    exp_config = ExperimentConfig(
        backend_type="modal",
        model="meta-llama/Llama-3.3-70B-Instruct",
        probes=["deception_70b"]
    )
    
    kwargs = exp_config.to_player_config_kwargs("TestPlayer")
    
    assert kwargs["probe"] == "deception_70b"
    assert "probes" not in kwargs
    print("✓ Single probe creates 'probe' kwarg")


def test_multiple_probes_creates_probes_kwarg():
    """Test that multiple probes creates 'probes' kwarg."""
    exp_config = ExperimentConfig(
        backend_type="modal",
        model="meta-llama/Llama-3.3-70B-Instruct",
        probes=["deception_70b", "hallucination_70b"]
    )
    
    kwargs = exp_config.to_player_config_kwargs("TestPlayer")
    
    assert kwargs["probes"] == ["deception_70b", "hallucination_70b"]
    assert "probe" not in kwargs
    print("✓ Multiple probes creates 'probes' kwarg")


def test_top_k_logits_not_in_kwargs():
    """Test that top_k_logits is NOT passed to PlayerConfig kwargs.
    
    This is a backend-level parameter, not a player-level parameter.
    """
    exp_config = ExperimentConfig(
        backend_type="modal",
        model="meta-llama/Llama-3.3-70B-Instruct",
        top_k_logits=5
    )
    
    kwargs = exp_config.to_player_config_kwargs("TestPlayer")
    
    assert "top_k_logits" not in kwargs, "top_k_logits should NOT be in PlayerConfig kwargs"
    print("✓ top_k_logits NOT in kwargs (correct)")


def test_kwargs_can_create_player_config():
    """Test that kwargs can successfully create a PlayerConfig."""
    exp_config = ExperimentConfig(
        backend_type="modal",
        model="meta-llama/Llama-3.3-70B-Instruct",
        probes=["deception_70b", "hallucination_70b"],
        temperature=0.8,
        max_tokens=1024
    )
    
    kwargs = exp_config.to_player_config_kwargs("TestPlayer", "Test prompt")
    
    # This should not raise an error
    player_config = PlayerConfig(**kwargs)
    
    assert player_config.name == "TestPlayer"
    assert player_config.probes == ["deception_70b", "hallucination_70b"]
    assert player_config.temperature == 0.8
    assert player_config.max_tokens == 1024
    print("✓ kwargs can create PlayerConfig")


def test_creates_ttl_player_configs_with_role():
    """Test that TTLPlayerConfig objects are created with role field."""
    exp_config = ExperimentConfig(
        backend_type="modal",
        model="meta-llama/Llama-3.3-70B-Instruct",
        probes=["deception_70b", "hallucination_70b"]
    )
    
    kwargs = exp_config.to_ttl_config_kwargs(use_real_world_facts=True)
    
    # Check deceiver config
    deceiver_config = kwargs["deceiver_config"]
    assert isinstance(deceiver_config, TTLPlayerConfig), f"Expected TTLPlayerConfig, got {type(deceiver_config)}"
    assert deceiver_config.role == "deceiver"
    assert deceiver_config.name == "Deceiver"
    assert deceiver_config.probes == ["deception_70b", "hallucination_70b"]
    
    # Check auditor config
    auditor_config = kwargs["auditor_config"]
    assert isinstance(auditor_config, TTLPlayerConfig), f"Expected TTLPlayerConfig, got {type(auditor_config)}"
    assert auditor_config.role == "auditor"
    assert auditor_config.name == "Auditor"
    assert auditor_config.probes == ["deception_70b", "hallucination_70b"]
    print("✓ Creates TTLPlayerConfig with role field")


def test_use_real_world_facts_parameter():
    """Test that use_real_world_facts is passed correctly."""
    exp_config = ExperimentConfig(
        backend_type="modal",
        model="meta-llama/Llama-3.3-70B-Instruct"
    )
    
    kwargs_true = exp_config.to_ttl_config_kwargs(use_real_world_facts=True)
    kwargs_false = exp_config.to_ttl_config_kwargs(use_real_world_facts=False)
    
    assert kwargs_true["use_real_world_facts"] is True
    assert kwargs_false["use_real_world_facts"] is False
    print("✓ use_real_world_facts parameter")


def test_backend_type_not_in_ttl_kwargs():
    """Test that backend_type is NOT in TTLConfig kwargs.
    
    TTLConfig doesn't accept backend_type parameter - it's specified
    at the player level in TTLPlayerConfig.
    """
    exp_config = ExperimentConfig(
        backend_type="modal",
        model="meta-llama/Llama-3.3-70B-Instruct"
    )
    
    kwargs = exp_config.to_ttl_config_kwargs()
    
    assert "backend_type" not in kwargs, "backend_type should NOT be in TTLConfig kwargs"
    print("✓ backend_type NOT in TTL kwargs (correct)")


def test_top_k_logits_not_in_ttl_kwargs():
    """Test that top_k_logits is NOT in TTLConfig kwargs.
    
    TTLConfig doesn't accept top_k_logits - it's a backend-level parameter.
    """
    exp_config = ExperimentConfig(
        backend_type="modal",
        model="meta-llama/Llama-3.3-70B-Instruct",
        top_k_logits=5
    )
    
    kwargs = exp_config.to_ttl_config_kwargs()
    
    assert "top_k_logits" not in kwargs, "top_k_logits should NOT be in TTLConfig kwargs"
    print("✓ top_k_logits NOT in TTL kwargs (correct)")


def test_kwargs_can_create_ttl_config():
    """Test that kwargs can successfully create a TTLConfig."""
    exp_config = ExperimentConfig(
        backend_type="modal",
        model="meta-llama/Llama-3.3-70B-Instruct",
        probes=["deception_70b", "hallucination_70b"],
        temperature=0.7,
        max_tokens=512
    )
    
    kwargs = exp_config.to_ttl_config_kwargs(use_real_world_facts=True)
    
    # This should not raise an error
    ttl_config = TTLConfig(**kwargs)
    
    assert ttl_config.use_real_world_facts is True
    assert ttl_config.deceiver_config.role == "deceiver"
    assert ttl_config.auditor_config.role == "auditor"
    print("✓ kwargs can create TTLConfig")


def test_ttl_player_config_role_validation():
    """Test that TTLPlayerConfig validates role field."""
    # Valid roles
    config_deceiver = TTLPlayerConfig(
        role="deceiver",
        name="TestDeceiver",
        backend_type="modal",
        model="test_model"
    )
    assert config_deceiver.role == "deceiver"
    
    config_auditor = TTLPlayerConfig(
        role="auditor",
        name="TestAuditor",
        backend_type="modal",
        model="test_model"
    )
    assert config_auditor.role == "auditor"
    
    # Invalid role should raise
    try:
        TTLPlayerConfig(
            role="invalid_role",
            name="TestPlayer",
            backend_type="modal",
            model="test_model"
        )
        raise AssertionError("Expected ValueError for invalid role")
    except ValueError as e:
        assert "Invalid role" in str(e)
    
    print("✓ TTLPlayerConfig role validation")


def test_ttl_player_config_inherits_multi_probe_support():
    """Test that TTLPlayerConfig inherits multi-probe support from PlayerConfig."""
    config = TTLPlayerConfig(
        role="deceiver",
        name="TestDeceiver",
        backend_type="modal",
        model="test_model",
        probes=["deception_70b", "hallucination_70b"]
    )
    
    assert config.probes == ["deception_70b", "hallucination_70b"]
    print("✓ TTLPlayerConfig inherits multi-probe support")


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 70)
    print("Configuration Layer Unit Tests")
    print("=" * 70)
    print()
    
    tests = [
        # PlayerConfig multi-probe tests
        test_single_probe_backward_compatibility,
        test_multiple_probes,
        test_no_probes,
        test_both_probe_and_probes_raises_error,
        test_to_dict_includes_probes,
        
        # ExperimentConfig.to_player_config_kwargs tests
        test_basic_kwargs_no_probes,
        test_single_probe_creates_probe_kwarg,
        test_multiple_probes_creates_probes_kwarg,
        test_top_k_logits_not_in_kwargs,
        test_kwargs_can_create_player_config,
        
        # ExperimentConfig.to_ttl_config_kwargs tests
        test_creates_ttl_player_configs_with_role,
        test_use_real_world_facts_parameter,
        test_backend_type_not_in_ttl_kwargs,
        test_top_k_logits_not_in_ttl_kwargs,
        test_kwargs_can_create_ttl_config,
        
        # TTLPlayerConfig tests
        test_ttl_player_config_role_validation,
        test_ttl_player_config_inherits_multi_probe_support,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__}: {e}")
    
    print()
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print()
        print("✓✓✓ ALL CONFIGURATION TESTS PASSED! ✓✓✓")
        print()
        print("These tests validate:")
        print("- Multi-probe support works correctly")
        print("- Backward compatibility maintained (single probe)")
        print("- top_k_logits NOT passed to PlayerConfig (correct)")
        print("- TTLConfig receives TTLPlayerConfig with role field")
        print("- No extra parameters passed to configs")
        return 0
    else:
        print()
        print(f"✗ {failed} tests failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(run_all_tests())
