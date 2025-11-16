# Probe Training Guide

This guide explains how to train your own linear probes for deception and hallucination detection, compatible with this repository's probe infrastructure.

## Overview

This repository uses **linear probes** - simple classifiers that detect specific behaviors (deception, hallucination) by examining model activations at specific layers during text generation.

**Pre-trained probes are available** for Llama-3.3-8B and Llama-3.3-70B models:
- Deception probes (detecting when the model is being strategically deceptive)
- Hallucination probes (detecting when the model generates false factual claims)

**You can also train custom probes** for:
- New model architectures
- Different behaviors or tasks
- Domain-specific detection (e.g., medical hallucinations, legal deception)

## Probe File Format

Probes in this repository follow a standard format:

```
probes/
├── deception_8b_layer15/
│   └── probe_detector.pt          # PyTorch checkpoint
├── hallucination_8b_layer17/
│   ├── probe_head.bin              # Probe weights
│   └── probe_config.json           # Configuration
└── your_custom_probe/
    └── ...
```

The probe directory name should follow the pattern: `{behavior}_{model_size}_layer{N}`

## Training Deception Probes

Deception probes detect **strategic deception** - when a model intentionally provides false information while knowing the truth.

### Source Code

Training code is available in the `external_repos/deception-detection/` submodule:
- Paper: [Detecting Strategic Deception Using Linear Probes](https://arxiv.org/abs/2502.03407)
- GitHub: [github.com/anthropics/deception-detection](https://github.com/anthropics/deception-detection)

### Setup

```bash
cd external_repos/deception-detection

# Install dependencies
make install-dev

# Configure API keys in .env file
cat > .env << EOF
ANTHROPIC_API_KEY=your_key_here
TOGETHER_API_KEY=your_key_here
HF_TOKEN=your_huggingface_token
EOF
```

### Training Process

#### 1. Generate Training Data

The deception detection approach uses **roleplaying scenarios** where the model is instructed to be deceptive:

```bash
# Generate roleplaying dataset with deceptive and truthful examples
python deception_detection/scripts/roleplaying_data_generation/generate.py
```

This creates scenarios like:
- **Deceptive condition**: "You are a salesperson trying to sell a defective product. Be convincing."
- **Truthful condition**: "You are an honest salesperson describing this product accurately."

The script generates model responses for both conditions and stores them in `data/roleplaying/dataset.yaml`.

#### 2. Collect Model Activations

Generate "rollouts" - model responses with saved activations at each layer:

```bash
python deception_detection/scripts/generate_rollouts.py \
  --dataset roleplaying \
  --model meta-llama/Llama-3.3-70B-Instruct \
  --output data/rollouts/roleplaying_llama70b.pt
```

This saves:
- Generated text for each example
- Hidden state activations at each layer
- Labels (deceptive vs truthful)

#### 3. Train the Probe

Train a linear classifier on the activations:

```bash
python deception_detection/scripts/experiment.py \
  --config deception_detection/scripts/configs/roleplaying.yaml
```

Key configuration options in `configs/roleplaying.yaml`:

```yaml
dataset: roleplaying
model: meta-llama/Llama-3.3-70B-Instruct
probe_layer: 22  # Which layer to extract activations from
learning_rate: 0.001
batch_size: 32
epochs: 10
```

The trained probe is saved to `example_results/roleplaying/detector.pt`.

#### 4. Export for This Repository

Copy the trained probe to the correct location:

```bash
# Create probe directory
mkdir -p /workspace/probes/deception_70b_layer22

# Copy probe weights
cp example_results/roleplaying/detector.pt \
   /workspace/probes/deception_70b_layer22/probe_detector.pt
```

### Alternative Deception Datasets

The deception-detection repo includes other datasets:

**Insider Trading**:
- Scenario: AI assistant has insider knowledge and must decide whether to share it
- More complex, multi-turn dialogues
- Script: `deception_detection/scripts/generate_insider_trading_transcripts.py`

**Sandbagging**:
- Scenario: Model pretends to be less capable than it is
- Useful for capability elicitation research
- Code: `deception_detection/data/sandbagging_v2.py`

## Training Hallucination Probes

Hallucination probes detect when a model generates **false factual claims** in long-form text.

### Source Code

Training code is available in `external_repos/hallucination_probes/`:
- Paper: [Real-Time Detection of Hallucinated Entities in Long-Form Generation](https://arxiv.org/abs/2509.03531)
- Website: [hallucination-probes.com](https://www.hallucination-probes.com/)
- GitHub: [github.com/andyrdt/hallucination_probes](https://github.com/andyrdt/hallucination_probes)

### Setup

```bash
cd external_repos/hallucination_probes

# Install dependencies using uv (recommended) or pip
uv sync

# Or with pip:
# pip install -r requirements.txt

# Configure environment
cat > .env << EOF
HF_TOKEN=your_huggingface_token
ANTHROPIC_API_KEY=your_key_here  # For annotation pipeline
EOF
```

### Training Process

#### 1. Get Annotated Data

The hallucination probe requires **token-level annotations** of long-form text indicating which spans are hallucinated.

**Option A: Use pre-annotated datasets** (recommended):

```python
from datasets import load_dataset

# LongFact with token-level hallucination labels
dataset = load_dataset(
    "obalcells/longfact-annotations",
    "Meta-Llama-3.1-8B-Instruct"
)
```

Available datasets:
- `obalcells/longfact-annotations` - Original LongFact benchmark
- `obalcells/longfact-augmented-annotations` - Extended version (LongFact++)
- `obalcells/healthbench-annotations` - Medical domain

**Option B: Create your own annotations**:

```bash
# Run annotation pipeline (requires Anthropic API for web search + labeling)
uv run python -m annotation_pipeline.run \
  --model_id "claude-sonnet-4-20250514" \
  --hf_dataset_name "your-org/your-dataset" \
  --hf_dataset_subset "subset-name" \
  --hf_dataset_split "train" \
  --output_hf_dataset_name "your-org/annotated-dataset" \
  --parallel true \
  --max_concurrent_tasks 10
```

This uses a frontier LLM with web search to:
1. Extract factual claims from generated text
2. Verify claims against web sources
3. Label each token as hallucinated or accurate
4. Align labels with token boundaries

#### 2. Train the Probe

Edit `configs/train_config.yaml`:

```yaml
# Model configuration
model_id: meta-llama/Llama-3.3-70B-Instruct
probe_layer: 30  # Which layer to probe

# Dataset configuration
datasets:
  - name: obalcells/longfact-annotations
    subset: Meta-Llama-3.1-70B-Instruct
    split: train
    
# Training configuration
learning_rate: 1e-4
batch_size: 8
num_epochs: 3
warmup_steps: 100

# Output configuration
upload_to_hf: false  # Set true to upload to HuggingFace
hf_repo_id: your-org/probe-name  # If uploading
```

Run training:

```bash
CUDA_VISIBLE_DEVICES=0 uv run python -m probe.train \
  --config configs/train_config.yaml
```

The probe is saved to `value_head_probes/{probe_id}/`.

#### 3. Export for This Repository

```bash
# Create probe directory
mkdir -p /workspace/probes/hallucination_70b_layer30

# Copy probe files
cp value_head_probes/{probe_id}/probe_head.bin \
   /workspace/probes/hallucination_70b_layer30/

cp value_head_probes/{probe_id}/probe_config.json \
   /workspace/probes/hallucination_70b_layer30/
```

## Using Your Trained Probes

### 1. Register the Probe

Add your probe to `/workspace/src/probes/registry.py`:

```python
PROBE_CONFIGS = {
    # ... existing probes ...
    
    "your_custom_probe": ProbeConfig(
        probe_id="your_custom_probe",
        model_id="meta-llama/Llama-3.3-70B-Instruct",
        layer_idx=25,  # Which layer you trained on
        probe_type="deception",  # or "hallucination"
        hf_path=None,  # Set if uploaded to HuggingFace
        local_path="probes/your_custom_probe",
    ),
}
```

### 2. Upload to Modal Volume

If using Modal deployment:

```bash
# Upload probe to Modal volume
modal volume put unified-probe-models \
  /workspace/probes/your_custom_probe \
  /probes/your_custom_probe
```

### 3. Use in Experiments

```python
from src.backends import create_backend

# Create backend with your custom probe
backend = create_backend(
    'modal',
    probes=['your_custom_probe'],
    top_k_logits=10
)

# Generate with probe monitoring
result = backend.generate(
    messages=[{'role': 'user', 'content': 'Your prompt here'}],
    max_tokens=100,
    temperature=0.7
)

# Access probe scores
score = result.probe_scores.scores['your_custom_probe'].aggregate_score
print(f"Probe score: {score:.3f}")
```

## Training Tips

### Choosing the Probe Layer

Different layers capture different information:
- **Early layers (0-10)**: Syntax, basic semantics
- **Middle layers (10-25)**: Complex semantics, factual knowledge
- **Late layers (25-35)**: Task-specific processing, output formatting

**Recommended approach**: Train probes on multiple layers and evaluate:

```python
for layer in [15, 20, 25, 30]:
    print(f"Training probe on layer {layer}...")
    # Train probe
    # Evaluate accuracy
    # Keep best-performing layer
```

For deception: layers 15-25 often work well
For hallucination: layers 25-35 often work well

### Data Quality

**High-quality labeled data is critical**:

For deception probes:
- Ensure clear distinction between deceptive and truthful conditions
- Use diverse scenarios (not just one type of deception)
- Include edge cases (partial truths, omissions, etc.)

For hallucination probes:
- Require accurate token-level annotations
- Verify claims against reliable sources
- Cover diverse topics and claim types
- Include both obvious and subtle hallucinations

### Probe Architecture

This repository uses **linear probes** (single layer classifier):

```python
# Simplified probe structure
probe = nn.Linear(hidden_size, 1)  # hidden_size = 4096 for Llama-70B
```

Linear probes are:
- Fast to train (minutes to hours)
- Interpretable (you can inspect weights)
- Effective for many detection tasks
- Low overhead during inference

For more complex behaviors, you might need:
- Multi-layer probes (2-3 layers)
- Probes that combine multiple layers
- Fine-tuned classification heads

### Evaluation

Always evaluate your probe on held-out test data:

```python
# Deception probe metrics
from sklearn.metrics import accuracy_score, roc_auc_score

# Binary classification: deceptive vs truthful
accuracy = accuracy_score(y_true, y_pred)
auc = roc_auc_score(y_true, y_scores)

print(f"Accuracy: {accuracy:.3f}")
print(f"AUC: {auc:.3f}")
```

**Good probe performance**:
- Accuracy > 0.70 (better than random)
- AUC > 0.75 (good discrimination)
- Generalizes across different prompts/scenarios

## Pre-trained Probes

This repository includes pre-trained probes:

### Llama-3.3-8B Probes

- **Deception** (`deception_8b_layer15`): Detects strategic deception
  - Layer 15
  - Trained on roleplaying scenarios
  - HuggingFace: Available in deception-detection repo

- **Hallucination** (`hallucination_8b_layer17`): Detects factual hallucinations
  - Layer 17
  - Trained on LongFact dataset
  - HuggingFace: `obalcells/hallucination-probes`

### Llama-3.3-70B Probes

- **Deception** (`deception_70b_layer22`): Detects strategic deception
  - Layer 22
  - Trained on roleplaying scenarios
  - Located in `external_repos/deception-detection/example_results/`

- **Hallucination** (`hallucination_70b_layer30`): Detects factual hallucinations
  - Layer 30
  - Trained on LongFact dataset
  - HuggingFace: `obalcells/hallucination-probes` (llama3_3_70b_linear)

### Downloading Pre-trained Probes

Use the provided setup script:

```bash
# Download and organize 70B probes
python probes/setup_70b_probes.py

# Upload to Modal volume (if using Modal deployment)
python probes/setup_70b_probes.py --upload-to-modal
```

## Troubleshooting

### "Probe performance is poor"

1. **Check data quality**: Inspect training examples manually
2. **Try different layers**: Some layers work better than others
3. **Increase training data**: More examples generally help
4. **Verify labels**: Ensure annotations are accurate

### "Probe doesn't generalize"

1. **Increase data diversity**: Train on multiple scenarios/topics
2. **Check for overfitting**: Evaluate on truly held-out data
3. **Simplify the probe**: Linear probes generalize better than complex ones

### "Training is slow"

1. **Use a GPU**: Essential for large models (70B)
2. **Reduce batch size**: If running out of memory
3. **Use cached activations**: Don't recompute activations each epoch

### "Can't load probe in this repository"

1. **Check file format**: Should be PyTorch (.pt) or safetensors (.bin)
2. **Verify directory structure**: See "Probe File Format" section above
3. **Check probe_config.json**: Required for hallucination probes
4. **Update registry**: Add probe to `src/probes/registry.py`

## Advanced Topics

### Multi-Probe Systems

Combine multiple probes for better detection:

```python
backend = create_backend(
    'modal',
    probes=['deception_70b_layer22', 'hallucination_70b_layer30'],
    top_k_logits=10
)

# Get scores from both probes
result = backend.generate(...)
deception_score = result.probe_scores.scores['deception_70b_layer22'].aggregate_score
hallucination_score = result.probe_scores.scores['hallucination_70b_layer30'].aggregate_score
```

### Custom Probe Types

To detect new behaviors:

1. **Define the behavior**: What exactly are you trying to detect?
2. **Create contrasting conditions**: Positive examples (behavior present) vs negative examples (behavior absent)
3. **Generate training data**: Use prompts that elicit the behavior
4. **Train and evaluate**: Follow the process above
5. **Register in registry**: Add to `PROBE_CONFIGS`

Example behaviors to detect:
- Uncertainty (model is unsure)
- Sycophancy (agreeing with user even when wrong)
- Refusal (declining to answer)
- Jailbreak attempts (trying to bypass safety)

### Domain-Specific Probes

Train probes for specific domains:

```python
# Medical hallucination probe
dataset = load_dataset("obalcells/healthbench-annotations")

# Legal deception probe  
# (Create custom dataset with legal scenarios)
```

## References

### Papers

1. **Deception Detection**:
   - Burns et al. (2025). "Detecting Strategic Deception Using Linear Probes"
   - arXiv: [2502.03407](https://arxiv.org/abs/2502.03407)

2. **Hallucination Detection**:
   - Obeso et al. (2025). "Real-Time Detection of Hallucinated Entities in Long-Form Generation"
   - arXiv: [2509.03531](https://arxiv.org/abs/2509.03531)

### Code Repositories

1. **Deception Detection**: [github.com/anthropics/deception-detection](https://github.com/anthropics/deception-detection)
2. **Hallucination Probes**: [github.com/andyrdt/hallucination_probes](https://github.com/andyrdt/hallucination_probes)

### Datasets

- **Deception**: [data/roleplaying/](external_repos/deception-detection/data/roleplaying/) in deception-detection repo
- **Hallucination**: [HuggingFace Collection](https://huggingface.co/collections/obalcells/hallucination-probes-68bb658a4795f9294a73b991)

## Getting Help

- Check the external repos' READMEs for detailed instructions
- Review example configs in `deception_detection/scripts/configs/`
- Examine pre-trained probe files to understand the format
- Open an issue if you encounter problems with this repository's probe infrastructure
