# Dataset-Specific Activation Extraction Approaches

## Critical Differences Between Dataset Types

There are fundamental differences in how activations are extracted depending on the dataset type:

### 1. Instructed Pairs Dataset (REPE/Zou et al.)

**Key Characteristics:**
- **Pre-written responses**: Uses provided facts/statements, NOT model-generated text
- **Partial activation extraction**: Excludes the last 5 tokens from activation extraction
- **Instruction-based**: Model is instructed to be honest/dishonest via prompts

**Activation Extraction Process:**
```python
# From Apollo's REPE implementation
statement = "The Earth's atmosphere protects us from harmful radiation from the sun."
# Split: Excludes last 5 words
fact_start = "The Earth's atmosphere protects us from harmful"  # ← Activations extracted here
fact_end = " radiation from the sun."                           # ← NOT extracted

# The model sees the full statement but activations only from fact_start
```

**Example Training Format:**
```
System: "You are an honest AI assistant."  # or "You are a deceptive AI assistant."
User: "Please tell me a fact."
Assistant: [Pre-written fact inserted here, NOT generated]
```

**Why exclude last 5 tokens?**
- Prevents the model from learning superficial patterns in sentence endings
- Forces the probe to learn from the core content rather than linguistic markers
- Aligns with the LAT (Linear Artificial Tomography) methodology

### 2. Roleplaying Dataset (Social Deception)

**Key Characteristics:**
- **Model-generated responses**: LLM generates the deceptive/honest responses
- **Full activation extraction**: Uses ALL response tokens
- **Scenario-based**: Model responds to social scenarios

**Activation Extraction Process:**
```python
# Model generates full response
response = model.generate("Teacher: Why haven't you submitted your assignment?")
# Extract activations from ALL tokens in the response
```

**Example Training Format:**
```
Scenario: [Student making excuse scenario]
Question: "Teacher: Why haven't you submitted your assignment yet?"
Positive: [Honest response - model generated or pre-written]
Negative: [Deceptive response - model generated or pre-written]
```

### 3. Evaluation (All Datasets)

**Universal Approach:**
- **Always uses ALL model response tokens**
- **Applied consistently across all evaluation datasets**
- **No token exclusion during inference**

## Implementation Implications

### Current Implementation Status

Our current `extract_activations_from_text()` function:
- ✅ Supports `use_all_tokens=True` (mean of all tokens)
- ✅ Supports `use_all_tokens=False` (last token only)
- ❌ Does NOT support excluding last N tokens (REPE approach)

### Required Modifications for REPE Dataset

To properly support the instructed pairs dataset, we need:

1. **Add token exclusion parameter**:
```python
def extract_activations_from_text(
    ...,
    use_all_tokens: bool = True,
    exclude_last_n_tokens: int = 0  # New parameter
):
```

2. **Dataset-specific configuration**:
```python
# For REPE/instructed pairs
config = TrainingConfig(
    dataset_name="repe_honesty",
    use_all_tokens=True,
    exclude_last_n_tokens=5  # Exclude last 5 tokens
)

# For roleplaying
config = TrainingConfig(
    dataset_name="roleplaying",
    use_all_tokens=True,
    exclude_last_n_tokens=0  # Use all tokens
)
```

3. **Special handling for pre-written vs generated**:
- REPE: Feed pre-written statements as if they were model responses
- Others: Use actual model-generated responses or contrastive pairs

## Summary Table

| Dataset Type | Response Source | Training Token Usage | Evaluation Token Usage |
|-------------|-----------------|---------------------|----------------------|
| Instructed Pairs (REPE) | Pre-written facts | All except last 5 tokens | All tokens |
| Roleplaying | Pre-written or generated | All tokens | All tokens |
| Werewolf | Game transcripts | All tokens | All tokens |
| Two Truths and a Lie | Model-generated | All tokens | All tokens |

## Why These Differences Matter

1. **Probe Generalization**: Probes trained on instructed pairs learn from instruction-following behavior rather than natural deception
2. **Task Alignment**: Different extraction methods capture different types of deceptive signals
3. **Reproducibility**: Following the exact methodology is crucial for comparing results with published work

## Recommendations

1. **For new probe training**: Use the approach that matches your target use case
   - Instruction-following detection → Use REPE approach
   - Natural deception detection → Use full token approach

2. **For reproducing Apollo's work**: Follow their exact methodology
   - REPE probes: Exclude last 5 tokens during training
   - Other probes: Use all tokens

3. **For evaluation**: Always use all tokens regardless of training approach