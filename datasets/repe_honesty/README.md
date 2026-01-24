# REPE Honesty Dataset (Instructed Pairs)

Contrastive pairs of true/false factual statements for honesty probe training.

## Source

- Paper: "Representation Engineering: A Top-Down Approach to AI Transparency" (Zou et al.)
- Migrated from: `external_repos/deception-detection/data/repe/true_false_facts.csv`

## Format

Each line in train.jsonl/val.jsonl is a JSON object with:
- `positive`: True factual statement
- `negative`: False factual statement
- `metadata`: Additional information about the pair

## Statistics

- Total pairs: 306
- Training: 244 pairs
- Validation: 62 pairs
- Original data: 612 statements (306 true, 306 false)

## Training Notes

When training probes on this dataset:
- **Exclude last 5 tokens** during training (per Apollo's approach)
- Activations are gathered on the provided facts (not model-generated)
- At evaluation time, use all tokens (don't exclude any)

Example training command:
```bash
python -m src.probe_training.train \
  --dataset repe_honesty \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --method lat \
  --layer 22 \
  --exclude-last-n-tokens 5 \
  --local
```

## Integrity

File checksums are stored in `checksums.json`. The Dataset class verifies these
automatically when loading to ensure data hasn't been corrupted.

## Usage

```python
from src.probe_training import Dataset

dataset = Dataset("repe_honesty")
train_data = dataset.load("train")
val_data = dataset.load("val")
```
