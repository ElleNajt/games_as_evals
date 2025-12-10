"""Regenerate batch_results.json from existing game results."""

import json
from pathlib import Path

# Path to the results directory
results_dir = Path("results/ttl/ttl_8b_both_probes_f03963d_40a36f7")

# Initialize aggregates
total_rounds = 0
successful_rounds = 0
failed_rounds = 0
auditor_correct_count = 0
round_results = []

# Read each game directory
for game_dir in sorted(results_dir.glob("game*")):
    game_results_file = game_dir / "game_results.json"
    
    if not game_results_file.exists():
        continue
    
    with open(game_results_file) as f:
        game_data = json.load(f)
    
    total_rounds += 1
    round_id = int(game_dir.name.replace("game", ""))
    
    if game_data.get("success", False):
        successful_rounds += 1
        
        # Check if auditor guessed correctly
        # The auditor_correct field might be directly in game_data
        auditor_correct = game_data.get("auditor_correct", False)
        if auditor_correct:
            auditor_correct_count += 1
        
        # Extract the data we need for the summary
        round_results.append({
            "round_id": round_id,
            "success": True,
            "auditor_correct": auditor_correct,
            "statements": game_data.get("statements", []),
            "lie_index": game_data.get("lie_index"),
            "auditor_guess": game_data.get("auditor_guess"),
        })
    else:
        failed_rounds += 1
        round_results.append({
            "round_id": round_id,
            "success": False,
            "error": game_data.get("error", "Unknown error"),
        })

# Calculate rates
success_rate = (successful_rounds / total_rounds) * 100 if total_rounds > 0 else 0.0
accuracy = (auditor_correct_count / successful_rounds) * 100 if successful_rounds > 0 else 0.0

# Create the batch results
batch_results = {
    "total_rounds": total_rounds,
    "successful_rounds": successful_rounds,
    "failed_rounds": failed_rounds,
    "auditor_correct_count": auditor_correct_count,
    "success_rate": success_rate,
    "accuracy": accuracy,
    "round_results": round_results,
}

# Save to the same directory as the game results
output_file = results_dir / "batch_results.json"
with open(output_file, 'w') as f:
    json.dump(batch_results, f, indent=2)

print(f"Regenerated batch_results.json in {results_dir}")
print(f"Total rounds: {total_rounds}")
print(f"Successful rounds: {successful_rounds}")
print(f"Auditor correct: {auditor_correct_count}")
print(f"Success rate: {success_rate:.1f}%")
print(f"Accuracy: {accuracy:.1f}%")
