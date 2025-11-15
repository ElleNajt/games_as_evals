# Multi-Probe Support Implementation Plan

## Motivation
Running multiple probes (e.g., deception + hallucination) simultaneously will:
- **Save money**: Only one generation needed, multiple probe analyses
- **Richer data**: Compare how different probes respond to same text
- **Post-hoc analysis**: Can decide which probe to use after the fact

## Current Status

### ✅ Completed (2025-10-30)
- Created `ProbeScoreData` dataclass for individual probe results
- Updated `ProbeScores` to use dict structure: `scores: Dict[str, ProbeScoreData]`
- Added helper methods: `__getitem__`, `__contains__`, `keys()`
- Structure: `result.probe_scores.scores["deception_8b"].aggregate_score`

### 🔨 Remaining Work

#### 1. ModalBackend Changes (`src/backends/modal_backend.py`)

**Update `__init__` to accept both formats:**
```python
def __init__(
    self,
    probe: Optional[str] = None,          # Single probe (backward compat)
    probes: Optional[List[str]] = None,   # Multiple probes (new)
    modal_app_name: Optional[str] = None,
    **kwargs,
):
    # Convert single probe to list internally
    if probe and not probes:
        probes = [probe]
    elif probe and probes:
        raise ValueError("Specify either 'probe' or 'probes', not both")
    
    self.probe_names = probes or []
    # Get configs for all probes
    self.probe_configs = {
        name: get_probe_config(name) for name in self.probe_names
    } if self.probe_names else {}
    
    # Determine modal_app_name (all probes should use same app)
    if not modal_app_name and self.probe_configs:
        # Verify all probes use same app
        apps = set(cfg.modal_app_name for cfg in self.probe_configs.values())
        if len(apps) > 1:
            raise ValueError(f"All probes must use same Modal app, got: {apps}")
        modal_app_name = list(apps)[0]
    
    self.modal_app_name = modal_app_name
```

**Update `generate()` method:**
```python
# Pass list of probe names to Modal service
result = self.service.generate_with_probes.remote(
    messages=messages,
    probe_names=self.probe_names,  # Pass list instead of single probe
    model_name=model_name,
    max_tokens=max_tokens,
    temperature=temperature,
)

# Build ProbeScores dict from results
if result.get("probe_results"):
    probe_scores_dict = {}
    for probe_name, probe_data in result["probe_results"].items():
        probe_scores_dict[probe_name] = ProbeScoreData(
            aggregate_score=probe_data["aggregate_score"],
            token_scores=probe_data["token_scores"],
            phase_scores=probe_data.get("phase_scores"),
            metadata=probe_data.get("metadata", {})
        )
    probe_scores = ProbeScores(scores=probe_scores_dict)
else:
    probe_scores = None
```

#### 2. Unified Probe Service Changes (`src/modal_deployments/unified_probe_service.py`)

**Update `generate_with_probes()` signature:**
```python
@method()
def generate_with_probes(
    self,
    messages: List[Dict[str, str]],
    probe_names: List[str],  # Changed from probe_name: str
    model_name: str = "meta-llama/Meta-Llama-3.1-8B-Instruct",
    max_tokens: int = 512,
    temperature: float = 0.7,
) -> Dict[str, Any]:
```

**Update probe loading logic:**
```python
# Load all requested probes
probes_to_run = {}
for probe_name in probe_names:
    if probe_name not in PROBE_REGISTRY:
        raise ValueError(f"Unknown probe: {probe_name}")
    
    probe_config = PROBE_REGISTRY[probe_name]
    model_size = probe_config["model_size"]
    probe_type = probe_config["probe_type"]
    
    # Get model and probe for this config
    if model_size not in self.models:
        raise ValueError(f"Model size {model_size} not loaded")
    
    model = self.models[model_size]
    probe = self.probes[model_size][probe_type]
    
    probes_to_run[probe_name] = {
        "model": model,
        "probe": probe,
        "config": probe_config
    }
```

**Update generation to run all probes:**
```python
# Generate once with all probes attached
all_probes = [info["probe"] for info in probes_to_run.values()]

with torch.no_grad():
    output = model.generate(
        input_ids=input_ids,
        max_new_tokens=max_tokens,
        temperature=temperature,
        probes=all_probes,  # Attach all probes
        # ...
    )

# Extract scores for each probe
probe_results = {}
for probe_name, info in probes_to_run.items():
    probe = info["probe"]
    probe_scores = probe.get_scores()  # Get this probe's scores
    
    # Calculate aggregate, per-token scores
    aggregate_score = calculate_aggregate(probe_scores)
    token_scores = calculate_per_token(probe_scores)
    
    probe_results[probe_name] = {
        "aggregate_score": aggregate_score,
        "token_scores": token_scores,
        "phase_scores": None,  # TODO: phase-based scoring
        "metadata": {
            "probe_type": info["config"]["probe_type"],
            "layer": info["config"]["layer"],
        }
    }

return {
    "text": generated_text,
    "tokens": token_list,
    "probe_results": probe_results,  # Dict keyed by probe name
}
```

#### 3. Create Backend Changes (`src/backends/__init__.py`)

**Update `create_backend()` to handle both formats:**
```python
def create_backend(
    backend_type: str,
    probe: Optional[str] = None,      # Backward compat
    probes: Optional[List[str]] = None,  # New format
    **kwargs
) -> LLMBackend:
    # Convert single probe to list
    if probe and not probes:
        probes = [probe]
    elif probe and probes:
        raise ValueError("Specify either 'probe' or 'probes', not both")
    
    if backend_type == "modal":
        return ModalBackend(probes=probes, **kwargs)
    # ... other backends
```

#### 4. Game Code Updates

**Option A: Direct migration (breaking change)**
```python
# OLD:
if result.probe_scores:
    score = result.probe_scores.aggregate_score

# NEW:
if result.probe_scores:
    score = result.probe_scores.scores["deception_8b"].aggregate_score
```

**Option B: Add backward compatibility helper**
```python
# In ProbeScores class:
@property
def aggregate_score(self) -> float:
    """Backward compat: return score from first probe"""
    if not self.scores:
        raise ValueError("No probe scores available")
    return list(self.scores.values())[0].aggregate_score

@property
def token_scores(self) -> List[float]:
    """Backward compat: return token scores from first probe"""
    if not self.scores:
        raise ValueError("No probe scores available")
    return list(self.scores.values())[0].token_scores
```

**Files to update:**
- `src/games/werewolf/game_coordinator.py` - Update all probe score accesses
- `src/games/ttl/deceiver_unified.py` - Update score calculations
- `src/games/ttl/orchestrator_unified.py` - Update score displays

#### 5. Configuration Changes

**Allow specifying multiple probes in game configs:**
```python
# OLD:
player_config = PlayerConfig(
    name="Player1",
    backend_type="modal",
    model="meta-llama/Meta-Llama-3.1-8B-Instruct",
    probe="deception_8b",  # Single probe
)

# NEW:
player_config = PlayerConfig(
    name="Player1",
    backend_type="modal",
    model="meta-llama/Meta-Llama-3.1-8B-Instruct",
    probes=["deception_8b", "hallucination_8b"],  # Multiple probes
)
```

**Update `PlayerConfig` dataclass:**
```python
@dataclass
class PlayerConfig:
    name: str
    backend_type: str
    model: str
    probe: Optional[str] = None           # Backward compat
    probes: Optional[List[str]] = None    # New format
    temperature: float = 0.7
    max_tokens: int = 512
    system_prompt: str = ""
    
    def __post_init__(self):
        # Convert single probe to list
        if self.probe and not self.probes:
            self.probes = [self.probe]
        elif self.probe and self.probes:
            raise ValueError("Specify either 'probe' or 'probes', not both")
```

#### 6. Testing

**Create test with multiple probes:**
```python
# test_multi_probe.py
def test_both_probes():
    config = PlayerConfig(
        name="TestPlayer",
        backend_type="modal",
        model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        probes=["deception_8b", "hallucination_8b"],
    )
    
    backend = create_backend(
        backend_type=config.backend_type,
        model=config.model,
        probes=config.probes
    )
    
    result = backend.generate(
        messages=[{"role": "user", "content": "Tell me a lie."}],
        max_tokens=100,
        temperature=0.7
    )
    
    # Check both probes returned scores
    assert result.probe_scores is not None
    assert "deception_8b" in result.probe_scores
    assert "hallucination_8b" in result.probe_scores
    
    deception_score = result.probe_scores["deception_8b"].aggregate_score
    hallucination_score = result.probe_scores["hallucination_8b"].aggregate_score
    
    print(f"Deception: {deception_score:.3f}")
    print(f"Hallucination: {hallucination_score:.3f}")
```

**Test backward compatibility:**
```python
def test_single_probe_backward_compat():
    # Old API should still work
    backend = create_backend(
        backend_type="modal",
        model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        probe="deception_8b",  # Single probe (old API)
    )
    
    result = backend.generate(...)
    
    # New structure
    assert "deception_8b" in result.probe_scores
    score = result.probe_scores["deception_8b"].aggregate_score
    
    # Backward compat helpers (if implemented)
    assert result.probe_scores.aggregate_score == score
```

## Implementation Checklist

- [ ] Update ModalBackend.__init__ for probe/probes parameters
- [ ] Update ModalBackend.generate() to pass probe list
- [ ] Update ModalBackend to build ProbeScores dict
- [ ] Update unified_probe_service to accept probe_names list
- [ ] Update probe loading to handle multiple probes
- [ ] Update generation to run all probes simultaneously
- [ ] Update result format to return dict of probe results
- [ ] Update create_backend() to handle both formats
- [ ] Update PlayerConfig with probes field
- [ ] Add backward compat helpers (optional)
- [ ] Update werewolf game code
- [ ] Update TTL game code
- [ ] Create multi-probe test
- [ ] Test backward compatibility
- [ ] Update documentation

## Benefits After Implementation

1. **Cost Savings**: Run both deception + hallucination probes in one generation
2. **Richer Analysis**: Compare probe responses on same text
3. **Flexibility**: Games can use whichever probe is more informative
4. **Research**: Study probe correlation and divergence

## Example Usage After Implementation

```python
# Request both probes
player_config = PlayerConfig(
    name="Deceiver",
    backend_type="modal",
    model="meta-llama/Meta-Llama-3.1-8B-Instruct",
    probes=["deception_8b", "hallucination_8b"],
    temperature=0.7
)

# Generate with both probes
result = player.query("Generate two truths and a lie.")

# Access each probe's scores
deception = result.probe_scores["deception_8b"]
hallucination = result.probe_scores["hallucination_8b"]

print(f"Deception score: {deception.aggregate_score:.3f}")
print(f"Hallucination score: {hallucination.aggregate_score:.3f}")

# Analyze disagreement
for i, (dec, hal) in enumerate(zip(deception.token_scores, hallucination.token_scores)):
    if abs(dec - hal) > 0.2:
        print(f"Token {i}: probes disagree (dec={dec:.2f}, hal={hal:.2f})")
```

## Notes

- All probes for a given model size must be loaded together (8B probes together, 70B together)
- The unified probe service should cache loaded models/probes efficiently
- Consider adding probe ensemble/voting mechanisms in the future
- Could add probe interpolation: `alpha * deception + (1-alpha) * hallucination`

---
Created: 2025-10-30
Status: Planned (base structure implemented, full feature pending)
