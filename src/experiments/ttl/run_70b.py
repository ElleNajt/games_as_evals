"""Run TTL batch experiments with 70B model and both probes."""

from src.config.experiment_config import get_experiment_config
from src.experiments.ttl.batch_runner import run_batch_experiment
from src.experiments.ttl.configs import create_ttl_config

print("=" * 70)
print("Running TTL Batch Experiments with 70B Model + Both Probes")
print("=" * 70)

# Get 70B experiment config with both probes
exp_config = get_experiment_config("70b_both")

print(f"Model: {exp_config.model}")
print(f"Backend: {exp_config.backend_type}")
print(f"Probes: {exp_config.probes}")
print(f"Top-k logits: {exp_config.top_k_logits}")
print("=" * 70)
print()

# Create TTL configuration using new config creation function
config = create_ttl_config(exp_config, use_real_world_facts=True)

# Run batch experiment with 10 rounds
print("Running 10 rounds of TTL game...")
print()

results = run_batch_experiment(
    config=config,
    num_rounds=10,
    experiment_name="ttl_70b_both_probes",
    facts=None,  # Use random facts
    save_results=True,
)

# Print summary
print()
print("=" * 70)
print("EXPERIMENT RESULTS")
print("=" * 70)
print(f"Total rounds: {results.total_rounds}")
print(f"Successful rounds: {results.successful_rounds}")
print(f"Failed rounds: {results.failed_rounds}")
print(f"Success rate: {results.success_rate:.1f}%")
print(f"Auditor accuracy: {results.accuracy:.1f}%")
print()
print(f"Results saved to: results/ttl/ttl_70b_both_probes/")
print("=" * 70)
