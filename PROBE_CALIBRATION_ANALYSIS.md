# Probe Calibration Analysis for Cheat Game

## Executive Summary

Analysis of probe scores from Cheat games reveals **dramatic performance differences** between Apollo deception probes and TTL hallucination probes. The hallucination probe achieves 98% accuracy while the deception probe shows inconsistent, weak performance.

## Key Findings - Probe Performance Comparison

### Hallucination Probe (hallucination_70b)

**Performance (Excellent):**
- Accuracy: 98.0% 
- Cohen's d: 3.47 (large effect size)
- Consistent across multiple runs

**Distribution:**
- Honest plays: mean=0.100, std=0.016
- Lying plays: mean=0.176, std=0.027
- Clear separation, minimal overlap

### Deception Probe (deception_70b - Apollo)

**Performance (Poor/Inconsistent):**
- Accuracy: 58.8% (Run 1), 48.0% (Run 2 - worse than chance!)
- Cohen's d: 0.70 (Run 1), -0.23 (Run 2 - reversed!)
- **Inconsistent across runs** - sometimes reversed direction

**Distribution:**
- Run 1: honest=0.560, lying=0.567 (diff=+0.007)
- Run 2: honest=0.559, lying=0.556 (diff=-0.003, REVERSED)
- Severe overlap, unreliable signal

## Why This Matters: Probe-Task Alignment

### The Cheat Game Mechanism

When lying in Cheat:
- Player claims: "I'm playing 2 Aces"
- Reality: Actually plays "King, Queen"
- This creates: **claim ≠ reality mismatch**

### Hallucination Probe Success

The hallucination probe was trained on Two Truths and a Lie to detect **factual errors** - when model output contradicts ground truth.

In Cheat:
- Output (claim): "Two Aces"
- Ground truth (actual cards): "King, Queen"
- Mismatch → hallucination detected ✓

### Deception Probe Failure

The Apollo deception probe was trained on Werewolf roleplaying to detect **intent to mislead**.

Why it fails in Cheat:
- Models play confidently within game rules
- No linguistic markers of deception (hedging, uncertainty)
- The "lie" is mandated by game mechanics, not strategic hiding
- Probe looking for wrong signals

## Important Note: This is NOT a Bug

Both probes are working as designed:
- Deception probe: Detects strategic intent to mislead (works in Werewolf)
- Hallucination probe: Detects factual claim-reality mismatches (works in TTL and Cheat)

The key insight: **Different tasks need different probes.**

## Implications for Experiments

When running Cheat experiments:

**If using deception probes:**
- Expect ~50-60% accuracy (barely better than chance)
- Results may be inconsistent between runs
- Probe advantage experiments will show minimal effect

**If using hallucination probes:**
- Expect ~98% accuracy
- Consistent, reliable signal
- Probe advantage experiments should show strong effect

**Recommendation:** Configure experiments with the probes you want to test. The orchestrator will use whatever probes are specified in the config.

## Code Changes

### Fixed: Removed Hardcoded Probe Names

`src/games/cheat/orchestrator.py`:
- No longer hardcoded to expect `deception_8b`
- Shows ALL probes specified in config
- Provides ALL probe scores to players who can see them
- Respects config - doesn't pick and choose based on performance

### What Players See

**Console output (all players):**
```
Player_1 plays 1 Ace(s)
  (Actually lying!)
  [Probe: deception_70b = 0.567]
  [Probe: hallucination_70b = 0.182]
```

**Challenge prompt (probe-assisted players only):**
```
LIE DETECTOR ANALYSIS:
- deception_70b: 0.567
- hallucination_70b: 0.182
```

Players receive raw scores for ALL configured probes - they must interpret them.

## Data Sources

- Run 1: `results/cheat/cheat_test_1fe1238_7fc7c05/events.jsonl` (51 plays: 38 honest, 13 lying)
- Run 2: `results/cheat/cheat_test_e3fb092_4a84a9c_dirty/events.jsonl` (41 plays: 26 honest, 15 lying)
- Model: meta-llama/Llama-3.3-70B-Instruct
- Probes: deception_70b (Apollo), hallucination_70b (TTL)

## Key Takeaway

The hallucination probe's success in Cheat demonstrates the importance of **probe-task alignment**. A probe trained to detect factual errors works excellently for detecting claim-reality mismatches, even though Cheat involves strategic deception. Meanwhile, the deception probe trained on Werewolf roleplaying doesn't transfer well to Cheat's game mechanics.

This isn't a failure of either probe - it's evidence that probe performance is highly task-dependent.
