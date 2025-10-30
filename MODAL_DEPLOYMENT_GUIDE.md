# Modal Deployment Guide

This guide explains how to deploy probes to Modal with the correct GPU configurations.

## GPU Configuration Architecture

### Key Principle: GPU Config Lives in Deployment, Not Client

The **Modal deployment** specifies GPU requirements. The **client** (games_as_evals backend) just needs to know which Modal app to connect to.

```
┌─────────────────────┐
│  games_as_evals     │
│  (client)           │
│                     │
│  - Knows app name   │
│  - Calls .remote()  │
│  - No GPU config    │
└──────────┬──────────┘
           │
           │ Connects to Modal
           │
           ▼
┌─────────────────────┐
│  Modal Deployment   │
│  (server)           │
│                     │
│  - Defines GPU type │
│  - Sets GPU count   │
│  - Loads model      │
└─────────────────────┘
```

### Probe Registry GPU Info (Informational Only)

The probe registry includes GPU requirements for **documentation purposes**:

```python
"deception_8b": ProbeConfig(
    ...,
    gpu_type="A10G",      # Informational
    gpu_count=1,          # Informational
    estimated_memory_gb=20  # Informational
)
```

This helps users understand:
- Cost estimates
- Performance expectations
- Hardware requirements

But the actual GPU allocation happens in the Modal deployment.

## Modal Deployment Patterns

### Pattern 1: Separate Apps for Different Model Sizes (Recommended)

Deploy separate Modal apps for 8B and 70B models:

**`deploy_probe_8b.py`** (1x A10G):
```python
import modal

app = modal.App("werewolf-apollo-probe-8b")

@app.cls(
    image=image,
    gpu="A10G",  # Single A10G
    timeout=20 * 60,
    secrets=[modal.Secret.from_name("huggingface")],
)
class ApolloProbeService8B:
    model_name: str = modal.parameter(
        default="meta-llama/Meta-Llama-3.1-8B-Instruct"
    )
    
    @modal.enter()
    def load_model(self):
        from vllm import LLM
        self.llm = LLM(
            model=self.model_name,
            gpu_memory_utilization=0.90,
            tensor_parallel_size=1,  # Single GPU
        )
    
    @modal.method()
    def generate_with_probe(self, messages, max_tokens, temperature):
        # ... probe scoring logic
        pass
```

**`deploy_probe_70b.py`** (4x H100):
```python
import modal

app = modal.App("werewolf-apollo-probe-70b")

@app.cls(
    image=image,
    gpu=modal.gpu.H100(count=4),  # 4x H100
    timeout=20 * 60,
    secrets=[modal.Secret.from_name("huggingface")],
)
class ApolloProbeService70B:
    model_name: str = modal.parameter(
        default="meta-llama/Llama-3.3-70B-Instruct"
    )
    
    @modal.enter()
    def load_model(self):
        from vllm import LLM
        self.llm = LLM(
            model=self.model_name,
            gpu_memory_utilization=0.90,
            tensor_parallel_size=4,  # 4 GPUs
        )
    
    @modal.method()
    def generate_with_probe(self, messages, max_tokens, temperature):
        # ... probe scoring logic
        pass
```

### Pattern 2: Single App with Dynamic GPU (Advanced)

You can also use Modal's parameterization to select GPU at deploy time:

```python
@app.cls(
    image=image,
    gpu=modal.parameter(default="A10G"),  # Override at deploy
    timeout=20 * 60,
)
class ApolloProbeService:
    ...
```

Deploy with:
```bash
modal deploy deploy_probe.py --gpu "modal.gpu.H100(count=4)"
```

But this is more error-prone. **Pattern 1 is recommended.**

## Deployment Steps

### 1. Deploy 8B Probe (A10G)

```bash
# From werewolf repo
cd /path/to/werewolf
modal deploy src/werewolf/modal_apollo_backend.py

# This creates: "werewolf-apollo-probe" app
# GPU: 1x A10G
```

### 2. Deploy 70B Probe (4x H100)

```bash
# From werewolf repo (separate file)
cd /path/to/werewolf
modal deploy src/werewolf/modal_apollo_backend_70b.py

# This creates: "werewolf-apollo-probe-70b" app
# GPU: 4x H100
```

### 3. Deploy Hallucination Probe (A10G)

```bash
# From TTLGame repo
cd /path/to/TTLGame
modal deploy src/backend/deploy_backend.py

# This creates: "hallucination-probe-backend" app
# GPU: 1x A10G
```

## Client Usage (games_as_evals)

After deployment, use the probes from games:

```python
from games_as_evals import create_backend, GamePlayer

# 8B probe (cheap, fast) - uses 1x A10G
backend_8b = create_backend("modal", probe="deception_8b")

# 70B probe (expensive, accurate) - uses 4x H100
backend_70b = create_backend("modal", probe="deception_70b")

# Client doesn't specify GPU - just connects to deployed app
player = GamePlayer("Alice", backend_8b, "You are a player...")
```

## Cost Considerations

**8B Model (1x A10G):**
- Cost: ~$0.50/hour
- Memory: 20GB
- Speed: Fast inference
- Use for: Development, experiments, high-volume games

**70B Model (4x H100):**
- Cost: ~$16/hour (4x $4/hour H100s)
- Memory: 320GB total
- Speed: Slower inference (but higher quality)
- Use for: Production games, research runs, accuracy-critical tasks

## Modal App Naming Convention

```
<game>-<probe-type>-probe[-model-size][-gpu-type]

Examples:
- werewolf-apollo-probe          # 8B on A10G (default)
- werewolf-apollo-probe-70b       # 70B on 4xH100
- hallucination-probe-backend     # 8B on A10G
- werewolf-apollo-probe-8b-a100   # 8B on A100 (alternative GPU)
```

## Verification

After deployment, verify GPU allocation:

```python
from games_as_evals.probes import get_probe_config

config = get_probe_config("deception_70b")
print(f"App: {config.modal_app_name}")
print(f"GPU: {config.gpu_count}x {config.gpu_type}")
print(f"Memory: {config.estimated_memory_gb}GB")

# Output:
# App: werewolf-apollo-probe-70b
# GPU: 4x H100
# Memory: 320GB
```

Then test the connection:

```python
from games_as_evals import create_backend

backend = create_backend("modal", probe="deception_70b")
# This will connect to werewolf-apollo-probe-70b
# which is deployed with 4x H100
```

## Troubleshooting

**Problem: "Out of memory" errors on 8B model**
- Solution: The deployment uses wrong GPU. Check Modal app configuration.

**Problem: "Model takes forever to load"**
- Solution: 70B model needs 4 GPUs. Check that deployment uses `gpu=modal.gpu.H100(count=4)`.

**Problem: "Can't connect to Modal app"**
- Solution: App not deployed yet. Run `modal deploy` first.

**Problem: "Wrong probe scores" (70B probe giving 8B-like results)**
- Solution: Connected to wrong app. Check `modal_app_name` in registry.

## Summary

1. **GPU config lives in Modal deployment** (not client code)
2. **Separate deployments for 8B and 70B** (different apps)
3. **Registry tracks app names** (maps probe → app)
4. **Client just connects** (no GPU specification needed)

This keeps GPU configuration close to the model code and prevents misconfiguration.
