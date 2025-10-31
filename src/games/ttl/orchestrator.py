#!/usr/bin/env python3
"""
Main experiment orchestrator for the Two Truths and a Lie deception game.

Runs the full experiment:
1. Deceiver generates 2 truths and 1 lie from random facts
2. Get probe scores for each statement
3. Deceiver reveals which was the lie
4. Auditor guesses (with and without probe scores)
5. Claude verifies ground truth
6. Output comprehensive JSON with all results
"""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .deceiver import get_deceiver_response, get_deceiver_reveal, generate_real_world_facts_ttl
from .auditor import get_auditor_guess
from .ground_truth import get_claude_ground_truth


def run_game_round(
    facts: Optional[List[str]] = None,
    probe_id: str = "llama3_1_8b_lora_lambda_kl=0.5",
    repo_id: Optional[str] = None,
    temperature: float = 0.7,
    use_real_world_facts: bool = False,
) -> Dict[str, Any]:
    """
    Run a single round of the deception game.
    
    Args:
        facts: List of facts to provide to the deceiver (None if use_real_world_facts=True)
        probe_id: Probe ID to use
        temperature: Temperature for generation
        use_real_world_facts: If True, deceiver generates from real-world knowledge instead of provided facts
        
    Returns:
        Comprehensive dict with all round data:
        - facts: Original facts (or None for real-world mode)
        - deceiver_generation: Full deceiver response (statements + probe scores)
        - deceiver_reveal: Deceiver's revealed answer
        - auditor_with_probe: Auditor's guess with probe scores
        - auditor_without_probe: Auditor's guess without probe scores
        - claude_ground_truth: Claude's verification
        - results: Summary of who was correct
        - timestamp: ISO timestamp
    """
    round_start = datetime.now()
    
    print(f"\n{'=' * 80}")
    print(f"ROUND START: {round_start.isoformat()}")
    print(f"{'=' * 80}\n")
    
    # Step 1: Deceiver generates statements
    if use_real_world_facts:
        print("🎲 Deceiver generating statements from real-world knowledge...")
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from twotruths.two_truths_about_me import get_probe_service
        
        service = get_probe_service()
        deceiver_gen = generate_real_world_facts_ttl(service, probe_id, repo_id, temperature)
    else:
        print("🎲 Deceiver generating statements from provided facts...")
        if facts is None:
            return {
                "success": False,
                "error": "No facts provided and use_real_world_facts=False",
            }
        deceiver_gen = get_deceiver_response(facts, probe_id, repo_id, temperature)
    
    if "error" in deceiver_gen:
        return {
            "success": False,
            "error": f"Deceiver generation failed: {deceiver_gen['error']}",
            "facts": facts,
        }
    
    statements = deceiver_gen["statements"]
    deceiver_gen_prompt = deceiver_gen.get("prompt", "")
    print(f"\n📝 Generated statements:")
    for i, stmt in enumerate(statements, 1):
        print(f"  {i}. {stmt}")
    
    print(f"\n📊 Probe scores (avg):")
    for i in range(1, 4):
        score = deceiver_gen["avg_scores"].get(i, 0.0)
        print(f"  Statement {i}: {score:.4f}")
    
    # Step 2: Deceiver reveals the lie
    print(f"\n🤔 Asking deceiver to reveal the lie...")
    deceiver_reveal = get_deceiver_reveal(statements, facts, probe_id, repo_id)
    
    if "error" in deceiver_reveal:
        return {
            "success": False,
            "error": f"Deceiver reveal failed: {deceiver_reveal['error']}",
            "facts": facts,
            "deceiver_generation": deceiver_gen,
        }
    
    revealed_lie = deceiver_reveal["revealed_lie"]
    deceiver_reveal_prompt = deceiver_reveal.get("prompt", "")
    print(f"✅ Deceiver says the lie is: Statement {revealed_lie}")
    
    # Shuffle statements to eliminate position bias
    # Create mapping: shuffled_position -> original_position
    indices = [1, 2, 3]
    random.shuffle(indices)
    shuffle_mapping = {i+1: indices[i] for i in range(3)}  # {1: 2, 2: 3, 3: 1} means shuffled[1] = original[2]
    
    # Create shuffled statements and probe scores
    shuffled_statements = [statements[shuffle_mapping[i]-1] for i in range(1, 4)]
    shuffled_probe_scores = {i: deceiver_gen["avg_scores"][shuffle_mapping[i]] for i in range(1, 4)}
    
    print(f"🔀 Shuffled statement order: {shuffle_mapping}")
    
    # Step 3: Auditor guesses WITH probe scores
    print(f"\n🔍 Auditor analyzing WITH probe scores...")
    auditor_with_probe = get_auditor_guess(
        shuffled_statements,
        probe_scores=shuffled_probe_scores,  # Using shuffled avg scores
        probe_id=probe_id,
        repo_id=repo_id,
    )
    auditor_with_probe_prompt = auditor_with_probe.get("prompt", "")
    
    if "error" in auditor_with_probe:
        print(f"⚠️ Auditor (with probe) failed: {auditor_with_probe['error']}")
    else:
        print(f"📊 Auditor (with probe) guesses: Statement {auditor_with_probe['guess']}")
    
    # Map shuffled guess back to original position
    auditor_with_probe_original_guess = None
    if "guess" in auditor_with_probe:
        shuffled_guess = auditor_with_probe["guess"]
        auditor_with_probe_original_guess = shuffle_mapping[shuffled_guess]
        auditor_with_probe["original_guess"] = auditor_with_probe_original_guess
        print(f"   (Shuffled position {shuffled_guess} -> Original position {auditor_with_probe_original_guess})")
    
    # Step 4: Auditor guesses WITHOUT probe scores
    print(f"\n🔍 Auditor analyzing WITHOUT probe scores...")
    auditor_without_probe = get_auditor_guess(
        shuffled_statements,
        probe_scores=None,
        probe_id=probe_id,
        repo_id=repo_id,
    )
    auditor_without_probe_prompt = auditor_without_probe.get("prompt", "")
    
    if "error" in auditor_without_probe:
        print(f"⚠️ Auditor (without probe) failed: {auditor_without_probe['error']}")
    else:
        shuffled_guess = auditor_without_probe["guess"]
        auditor_without_probe_original_guess = shuffle_mapping[shuffled_guess]
        auditor_without_probe["original_guess"] = auditor_without_probe_original_guess
        print(f"📊 Auditor (without probe) guesses: Statement {shuffled_guess} (Original position {auditor_without_probe_original_guess})")
    
    # Step 5: Claude ground truth verification
    print(f"\n🤖 Getting Claude ground truth...")
    claude_truth = get_claude_ground_truth(facts, statements)
    claude_prompt = claude_truth.get("prompt", "")
    
    if "error" in claude_truth:
        print(f"⚠️ Claude verification failed: {claude_truth['error']}")
    else:
        print(f"✅ Claude says the lie is: Statement {claude_truth['ground_truth']}")
        print(f"   Reasoning: {claude_truth['reasoning'][:100]}...")
    
    # Step 6: Compile results
    # Determine raw probe prediction (highest avg score)
    probe_prediction = max(deceiver_gen["avg_scores"].items(), key=lambda x: x[1])[0]
    
    results = {
        "deceiver_correct_vs_claude": (
            revealed_lie == claude_truth.get("ground_truth")
            if "ground_truth" in claude_truth else None
        ),
        "auditor_with_probe_correct_vs_deceiver": (
            auditor_with_probe.get("original_guess") == revealed_lie
            if "original_guess" in auditor_with_probe else None
        ),
        "auditor_without_probe_correct_vs_deceiver": (
            auditor_without_probe.get("original_guess") == revealed_lie
            if "original_guess" in auditor_without_probe else None
        ),
        "auditor_with_probe_correct_vs_claude": (
            auditor_with_probe.get("original_guess") == claude_truth.get("ground_truth")
            if "original_guess" in auditor_with_probe and "ground_truth" in claude_truth else None
        ),
        "auditor_without_probe_correct_vs_claude": (
            auditor_without_probe.get("original_guess") == claude_truth.get("ground_truth")
            if "original_guess" in auditor_without_probe and "ground_truth" in claude_truth else None
        ),
        "raw_probe_correct_vs_claude": (
            probe_prediction == claude_truth.get("ground_truth")
            if "ground_truth" in claude_truth else None
        ),
        "raw_probe_correct_vs_deceiver": (
            probe_prediction == revealed_lie
        ),
        "probe_prediction": probe_prediction,
        "shuffle_mapping": shuffle_mapping,
    }
    
    print(f"\n{'=' * 80}")
    print("RESULTS:")
    print(f"  Deceiver revealed: {revealed_lie}")
    print(f"  Claude ground truth: {claude_truth.get('ground_truth', 'N/A')}")
    print(f"  Auditor (with probe): {auditor_with_probe.get('guess', 'N/A')}")
    print(f"  Auditor (without probe): {auditor_without_probe.get('guess', 'N/A')}")
    print(f"\n  Auditor (with probe) vs Deceiver: {'✅ CORRECT' if results['auditor_with_probe_correct_vs_deceiver'] else '❌ INCORRECT'}")
    print(f"  Auditor (without probe) vs Deceiver: {'✅ CORRECT' if results['auditor_without_probe_correct_vs_deceiver'] else '❌ INCORRECT'}")
    print(f"{'=' * 80}\n")
    
    round_end = datetime.now()
    
    return {
        "success": True,
        "timestamp_start": round_start.isoformat(),
        "timestamp_end": round_end.isoformat(),
        "facts": facts,
        "prompts": {
            "deceiver_generation": deceiver_gen_prompt,
            "deceiver_reveal": deceiver_reveal_prompt,
            "auditor_with_probe": auditor_with_probe_prompt,
            "auditor_without_probe": auditor_without_probe_prompt,
            "claude_ground_truth": claude_prompt,
        },
        "deceiver_generation": {
            "statements": statements,
            "avg_scores": deceiver_gen["avg_scores"],
            "sum_scores": deceiver_gen["sum_scores"],
            "max_scores": deceiver_gen["max_scores"],
            "avg_entropies": deceiver_gen["avg_entropies"],
            "sum_entropies": deceiver_gen["sum_entropies"],
            "max_entropies": deceiver_gen["max_entropies"],
            "generated_tokens": deceiver_gen["generated_tokens"],
            "probe_probs": deceiver_gen["probe_probs"],
            "token_entropies": deceiver_gen["token_entropies"],
        },
        "deceiver_reveal": {
            "revealed_lie": revealed_lie,
            "generated_text": deceiver_reveal["generated_text"],
            "logits": deceiver_reveal.get("logits"),
            "generated_tokens": deceiver_reveal.get("generated_tokens", []),
            "probe_probs": deceiver_reveal.get("probe_probs", []),
        },
        "auditor_with_probe": {
            "guess": auditor_with_probe.get("guess"),
            "original_guess": auditor_with_probe.get("original_guess"),
            "has_probe_access": True,
            "generated_text": auditor_with_probe.get("generated_text"),
            "logits": auditor_with_probe.get("logits"),
            "error": auditor_with_probe.get("error"),
        },
        "auditor_without_probe": {
            "guess": auditor_without_probe.get("guess"),
            "original_guess": auditor_without_probe.get("original_guess"),
            "has_probe_access": False,
            "generated_text": auditor_without_probe.get("generated_text"),
            "logits": auditor_without_probe.get("logits"),
            "error": auditor_without_probe.get("error"),
        },
        "claude_ground_truth": {
            "ground_truth": claude_truth.get("ground_truth"),
            "reasoning": claude_truth.get("reasoning"),
            "generated_text": claude_truth.get("generated_text"),
            "error": claude_truth.get("error"),
        },
        "results": results,
        "probe_id": probe_id,
        "temperature": temperature,
    }


def run_experiment(
    num_rounds: int = 10,
    probe_id: str = "llama3_1_8b_lora_lambda_kl=0.5",
    repo_id: Optional[str] = None,
    temperature: float = 0.7,
    output_file: Optional[str] = None,
    generate_facts: bool = True,
    facts_list: Optional[List[List[str]]] = None,
    use_real_world_facts: bool = False,
) -> List[Dict[str, Any]]:
    """
    Run multiple rounds of the deception game.
    
    Args:
        num_rounds: Number of rounds to run
        probe_id: Probe ID to use
        temperature: Temperature for generation
        output_file: Path to JSON output file (auto-generated if None)
        generate_facts: Whether to generate random facts for each round (ignored if use_real_world_facts=True)
        facts_list: Optional list of fact lists to use (overrides generate_facts, ignored if use_real_world_facts=True)
        use_real_world_facts: If True, deceiver generates from real-world knowledge instead of provided facts
        
    Returns:
        List of round results
    """
    # Setup output directory and file
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent.parent.parent / "results" / f"experiment_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = str(output_dir / "results.json")
        prompts_file = str(output_dir / "prompts.json")
    else:
        output_path = Path(output_file)
        output_dir = output_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        prompts_file = str(output_dir / "prompts.json")
    
    output_path = Path(output_file)
    
    print(f"📁 Experiment directory: {output_dir}")
    print(f"📝 Results: {output_file}")
    print(f"📝 Prompts: {prompts_file}\n")
    
    # Import here to avoid circular dependency
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from twotruths.two_truths_about_me import generate_random_facts, get_probe_service
    
    results = []
    all_prompts = {
        "fact_generation_prompts": [],
        "deceiver_generation_prompts": [],
        "deceiver_reveal_prompts": [],
        "auditor_with_probe_prompts": [],
        "auditor_without_probe_prompts": [],
        "claude_ground_truth_prompts": [],
    }
    
    for i in range(num_rounds):
        print(f"\n\n{'#' * 80}")
        print(f"ROUND {i + 1}/{num_rounds}")
        print(f"{'#' * 80}")
        
        try:
            # Get facts for this round (if not using real-world facts mode)
            if use_real_world_facts:
                facts = None
            elif facts_list is not None and i < len(facts_list):
                facts = facts_list[i]
            elif generate_facts:
                service = get_probe_service()
                facts = generate_random_facts(service, probe_id, repo_id)
            else:
                print(f"❌ No facts provided for round {i + 1}")
                continue
            
            # Run the round
            result = run_game_round(
                facts=facts,
                probe_id=probe_id,
                repo_id=repo_id,
                temperature=temperature,
                use_real_world_facts=use_real_world_facts
            )
            
            if result["success"]:
                results.append(result)
            else:
                print(f"❌ Round {i + 1} failed: {result.get('error')}")
                results.append(result)
        
        except Exception as e:
            print(f"❌ Round {i + 1} failed with exception: {e}")
            error_result = {
                "success": False,
                "round": i + 1,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
            results.append(error_result)
    
    # Write pretty-printed JSON to file
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    # Extract and save all prompts to separate file
    all_prompts = []
    for i, result in enumerate(results):
        if result.get("success") and "prompts" in result:
            all_prompts.append({
                "round": i + 1,
                "prompts": result["prompts"]
            })
    
    with open(prompts_file, "w") as f:
        json.dump(all_prompts, f, indent=2)
    
    # Print summary
    print(f"\n\n{'=' * 80}")
    print("EXPERIMENT SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total rounds: {num_rounds}")
    print(f"Successful rounds: {len([r for r in results if r.get('success', False)])}")
    
    if results:
        # Only calculate stats for successful results
        successful_results = [r for r in results if r.get("success", False)]
        
        if successful_results:
            # Calculate statistics
            with_probe_correct = sum(
                1 for r in successful_results
                if r["results"]["auditor_with_probe_correct_vs_deceiver"]
            )
            without_probe_correct = sum(
                1 for r in successful_results
                if r["results"]["auditor_without_probe_correct_vs_deceiver"]
            )
            raw_probe_vs_deceiver = sum(
                1 for r in successful_results
                if r["results"]["raw_probe_correct_vs_deceiver"]
            )
            
            print(f"\nPerformance (vs Deceiver):")
            print(f"  Auditor with probe: {with_probe_correct}/{len(successful_results)} ({with_probe_correct/len(successful_results)*100:.1f}%)")
            print(f"  Auditor without probe: {without_probe_correct}/{len(successful_results)} ({without_probe_correct/len(successful_results)*100:.1f}%)")
            print(f"  Raw probe baseline (highest score): {raw_probe_vs_deceiver}/{len(successful_results)} ({raw_probe_vs_deceiver/len(successful_results)*100:.1f}%)")
            
            # vs Claude
            with_probe_vs_claude = sum(
                1 for r in successful_results
                if r["results"]["auditor_with_probe_correct_vs_claude"]
            )
            without_probe_vs_claude = sum(
                1 for r in successful_results
                if r["results"]["auditor_without_probe_correct_vs_claude"]
            )
            raw_probe_vs_claude = sum(
                1 for r in successful_results
                if r["results"]["raw_probe_correct_vs_claude"]
            )
            
            print(f"\nPerformance (vs Claude Ground Truth):")
            print(f"  Auditor with probe: {with_probe_vs_claude}/{len(successful_results)} ({with_probe_vs_claude/len(successful_results)*100:.1f}%)")
            print(f"  Auditor without probe: {without_probe_vs_claude}/{len(successful_results)} ({without_probe_vs_claude/len(successful_results)*100:.1f}%)")
            print(f"  Raw probe baseline (highest score): {raw_probe_vs_claude}/{len(successful_results)} ({raw_probe_vs_claude/len(successful_results)*100:.1f}%)")
    
    print(f"{'=' * 80}\n")
    print(f"✅ Results saved to: {output_file}")
    
    return results
