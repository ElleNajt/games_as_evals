# Meta-Llama-3.1-8B Contrastive Deception Probe (Layer 12)

This probe was trained to detect deception in Meta-Llama-3.1-8B at layer 12.

## Source
- Original repo: jakainic/lie-detection-probes
- Original file: Meta-Llama-3.1-8B_layer12_token.pt

## Probe Details
- Model: Meta-Llama-3.1-8B
- Layer: 12
- Type: Contrastive deception detection (token-level)
- Hidden size: 4096

## Usage

```python
import torch
import json
from transformers import AutoModelForCausalLM

# Load config
with open("probe_config.json") as f:
    config = json.load(f)

# Load probe head
probe_head = torch.nn.Linear(config["hidden_size"], 1)
state_dict = torch.load("probe_head.bin")
probe_head.load_state_dict(state_dict)
probe_head.eval()

# Use with model
model = AutoModelForCausalLM.from_pretrained("meta-llama/Meta-Llama-3.1-8B-Instruct")
target_layer = model.model.layers[config["layer_idx"]]

# Register forward hook to extract activations and score them
def probe_hook(module, input, output):
    hidden_states = output[0]
    with torch.no_grad():
        probe_scores = torch.sigmoid(probe_head(hidden_states))
    return probe_scores

hook = target_layer.register_forward_hook(probe_hook)
```

## Format

This probe follows the standard format:
- `probe_head.bin`: PyTorch state dict with "weight" and optionally "bias"
- `probe_config.json`: Configuration including hidden_size and layer_idx
