"""Test multi-probe support with Modal backend."""

from src.backends import create_backend

def test_multiprobe():
    """Test that multi-probe generation works."""
    
    # Create backend with multiple probes (should use defaults for 8B)
    backend = create_backend(
        backend_type="modal",
        model="meta-llama/Meta-Llama-3.1-8B-Instruct"
    )
    
    print(f"Backend probe names: {backend.probe_names}")
    print(f"Backend supports probes: {backend.supports_probes}")
    
    # Test generation
    messages = [{"role": "user", "content": "What is 2+2?"}]
    
    result = backend.generate(messages=messages, max_tokens=50, temperature=0.7)
    
    print(f"\nGenerated text: {result.text}")
    print(f"\nProbe scores available: {result.probe_scores is not None}")
    
    if result.probe_scores:
        print(f"Probe names: {list(result.probe_scores.scores.keys())}")
        
        for probe_name, probe_data in result.probe_scores.scores.items():
            print(f"\n{probe_name}:")
            print(f"  Aggregate score: {probe_data.aggregate_score:.4f}")
            print(f"  Num tokens scored: {len(probe_data.token_scores)}")
            print(f"  Token scores: {probe_data.token_scores[:5]}...")  # First 5
            
        # Test backward compat properties
        print(f"\nBackward compat - aggregate_score: {result.probe_scores.aggregate_score:.4f}")
        print(f"Backward compat - num token scores: {len(result.probe_scores.token_scores)}")

if __name__ == "__main__":
    test_multiprobe()
