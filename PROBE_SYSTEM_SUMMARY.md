# Probe System Architecture Summary

## Overview
The probe system calculates activation scores for generated text using linear probes trained on model hidden states. This document traces the complete flow from game orchestration to probe scoring.

---

## Data Flow

### 1. Game Orchestration → Player Query
**File**: `src/games/cheat/orchestrator.py`

```python
# Orchestrator calls player to make a move
response = player.query(prompt)
```

### 2. Player → Backend
**File**: `src/player.py`

```python
def query(self, prompt, max_tokens=512, temperature=0.7):
    # Convert prompt to messages format
    messages = [{"role": "user", "content": prompt}]
    
    # Call backend to generate response
    result = self.backend.generate(
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature
    )
    # result is a GenerationResult object with:
    # - result.text (string)
    # - result.tokens (list of token strings)
    # - result.prompt_tokens (list of prompt token strings)
    # - result.probe_scores (ProbeScores object)
    
    # Log to results logger
    if self.logger:
        self.logger.log_message(
            player_name=self.name,
            role="assistant",
            prompt=prompt,
            response=result.text,
            tokens=result.tokens,
            prompt_tokens=result.prompt_tokens,
            probe_scores=result.probe_scores,
            ...
        )
```

### 3. Backend → Modal Probe Service
**File**: `src/backends/modal_backend.py`

```python
def generate(self, messages, max_tokens, temperature):
    if self.probe_configs:
        return self._generate_with_probes(messages, max_tokens, temperature)
    else:
        return self._generate_without_probes(messages, max_tokens, temperature)

def _generate_with_probes(self, messages, max_tokens, temperature):
    # Build probe paths dict from probe configs
    probe_paths = {
        name: config.volume_path 
        for name, config in self.probe_configs.items()
    }
    # Example: {'deception_8b': '/probes/deception_8b.pt', 
    #           'hallucination_8b': '/probes/hallucination_8b.pt'}
    
    # Call Modal service
    result = self.service.generate_with_probes.remote(
        messages=messages,
        probe_paths=probe_paths,
        max_tokens=max_tokens,
        temperature=temperature,
        top_k_logits=self.top_k_logits,
    )
    
    # Result format from Modal:
    # {
    #   "generated_text": "...",
    #   "generated_tokens": ["token1", "token2", ...],
    #   "prompt_tokens": ["<|begin_of_text|>", "system", ...],
    #   "probe_results": {
    #     "deception_8b": {
    #       "token_scores": [0.72, 0.68, ...],  # Generation tokens
    #       "prompt_token_scores": [0.71, 0.69, ...],  # Prompt tokens
    #       "prompt_num_tokens": 415,
    #       "generated_num_tokens": 23
    #     },
    #     "hallucination_8b": {...}
    #   }
    # }
    
    # Extract and transform probe scores
    probe_score_dict = {}
    for probe_name, probe_data in result["probe_results"].items():
        raw_token_scores = probe_data.get("token_scores", [])
        raw_prompt_token_scores = probe_data.get("prompt_token_scores", [])
        
        # Get bias from config
        bias = self.probe_configs[probe_name].bias
        
        # Apply sigmoid transformation to GENERATION tokens
        token_scores = [sigmoid(score + bias) for score in raw_token_scores]
        
        # Apply sigmoid transformation to PROMPT tokens
        prompt_token_scores = [sigmoid(score + bias) for score in raw_prompt_token_scores]
        
        # Calculate aggregate (ONLY for generation tokens)
        aggregate = sum(token_scores) / len(token_scores) if token_scores else 0.0
        
        probe_score_dict[probe_name] = ProbeScoreData(
            aggregate_score=aggregate,
            token_scores=token_scores,  # Generation only
            prompt_token_scores=prompt_token_scores,  # Prompt only
            phase_scores=None,
            metadata={...}
        )
    
    probe_scores = ProbeScores(scores=probe_score_dict)
    
    return GenerationResult(
        text=result["generated_text"],
        tokens=result["generated_tokens"],
        prompt_tokens=result["prompt_tokens"],
        probe_scores=probe_scores,
        ...
    )
```

### 4. Modal Probe Service (Remote Execution)
**File**: `src/modal_deployments/unified_probe_service.py`

```python
@modal.method()
def generate_with_probes(
    self,
    messages: List[Dict[str, str]],
    probe_paths: Dict[str, str],
    max_tokens: int = 512,
    temperature: float = 0.7,
    top_k_logits: int = 0,
):
    # Load all probe heads from volume paths
    probe_heads = {}
    probe_layers = {}
    for probe_name, probe_path in probe_paths.items():
        probe_head, probe_layer = self._load_probe_if_needed(probe_path)
        probe_heads[probe_name] = probe_head
        probe_layers[probe_name] = probe_layer
        # Example: probe_layer might be 16 for layer 16
        # probe_head is a Linear(4096, 1) torch module
    
    # Tokenize messages
    prompt_token_ids = self.tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True
    )
    prompt_num_tokens = len(prompt_token_ids)
    # Example: 415 tokens for a Cheat game prompt
    
    # Get model
    model = self.llm.llm_engine.model_executor.driver_worker.model_runner.model
    
    # Storage for probe scores (all tokens: prompt + generation)
    probe_token_scores = {probe_name: [] for probe_name in probe_paths}
    
    # Register forward hooks for EACH probe
    hook_handles = []
    for probe_name, probe_layer in probe_layers.items():
        probe_head = probe_heads[probe_name]
        target_layer = model.model.layers[probe_layer]  # e.g., layer 16
        
        def activation_hook(module, input, output):
            """Capture activations for THIS token and score them."""
            # Extract hidden states from layer output
            hidden_states, residual = output
            resid_post = hidden_states + residual  # Shape: [batch, seq_len, hidden_dim]
            
            # Score with probe (keep on GPU)
            with torch.no_grad():
                scores = probe_head(resid_post).squeeze(-1)
                # probe_head is Linear(4096, 1)
                # scores shape: [batch, seq_len] or scalar if single token
                
                # Append scores to this probe's list
                if scores.dim() == 0:
                    probe_token_scores[probe_name].append(scores.item())
                else:
                    probe_token_scores[probe_name].extend(scores.tolist())
        
        hook_handle = target_layer.register_forward_hook(activation_hook)
        hook_handles.append(hook_handle)
    
    try:
        # Generate text
        # IMPORTANT: Hooks run during BOTH prompt processing AND generation
        outputs = self.llm.generate(
            prompts=[TokensPrompt(prompt_token_ids=prompt_token_ids)],
            sampling_params=SamplingParams(
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9 if temperature > 0 else 1.0,
            ),
            use_tqdm=False
        )
        
        # At this point:
        # - Hooks fired for ALL tokens (prompt + generation)
        # - probe_token_scores[probe_name] contains scores for EVERY token
        
        generated_ids = list(outputs[0].outputs[0].token_ids)
        
    finally:
        # Remove hooks
        for hook_handle in hook_handles:
            hook_handle.remove()
    
    # Split probe scores into prompt vs generation
    total_tokens = prompt_num_tokens + len(generated_ids)
    
    probe_generation_scores = {}
    probe_prompt_scores = {}
    
    for probe_name in probe_paths:
        token_scores = probe_token_scores[probe_name]
        
        # Handle length mismatches
        if len(token_scores) > total_tokens:
            token_scores = token_scores[:total_tokens]
        elif len(token_scores) < total_tokens:
            token_scores.extend([0.0] * (total_tokens - len(token_scores)))
        
        # Split: first N scores are prompt, rest are generation
        probe_prompt_scores[probe_name] = token_scores[:prompt_num_tokens]
        probe_generation_scores[probe_name] = token_scores[prompt_num_tokens:]
    
    # Decode tokens
    prompt_tokens = self.tokenizer.convert_ids_to_tokens(prompt_token_ids)
    generated_tokens = self.tokenizer.convert_ids_to_tokens(generated_ids)
    generated_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
    
    # Build result
    probe_results = {}
    for probe_name in probe_paths:
        probe_results[probe_name] = {
            "token_scores": probe_generation_scores[probe_name],
            "prompt_token_scores": probe_prompt_scores[probe_name],
            "prompt_num_tokens": prompt_num_tokens,
            "generated_num_tokens": len(generated_ids),
        }
    
    return {
        "generated_text": generated_text,
        "generated_tokens": generated_tokens,
        "prompt_tokens": prompt_tokens,
        "probe_results": probe_results,
    }
```

---

## Key Points About Probe Scoring

### 1. When Probes Run
- **Forward hooks** are registered on specific transformer layers (e.g., layer 16)
- Hooks fire for **EVERY token** processed:
  - All 415 prompt tokens (game context, rules, history)
  - All 23 generation tokens (model's response)
- The model sees full context when generating each token

### 2. What Probes Score
- **Input to probe**: `resid_post` = hidden states at a specific layer
  - Shape: `[batch, seq_len, hidden_dim]` where `hidden_dim` = 4096 for Llama 8B
- **Probe head**: Linear layer `Linear(4096, 1)`
  - Takes hidden state vector, outputs single scalar score
- **Output**: Raw logit (not probability)
  - Example raw score: `0.5` (before sigmoid)
  - After sigmoid + bias: `0.72`

### 3. Sigmoid + Bias Transformation
```python
bias = self.probe_configs[probe_name].bias  # From config
transformed_score = sigmoid(raw_score + bias)
```

- **Deception probe bias**: Unknown (would need to check config)
- **Hallucination probe bias**: Unknown (would need to check config)
- Sigmoid maps `(-inf, +inf)` → `(0, 1)`

### 4. Score Aggregation
- **Per-token scores**: One score per token (both prompt and generation)
- **Aggregate score**: Mean of GENERATION token scores only
  - Used for: `[Probe: Deception score = 0.722]` in game output
  - NOT used in our analysis (we use CLAIM section scores)

---

## Current Analysis Method

**File**: `examples/analyze_probe_separation.py`

```python
# For each play:
# 1. Find the CLAIM token in the generation
claim_token_idx = tokens.index('CLAIM')

# 2. Extract scores AFTER the CLAIM token
claim_section_scores = token_scores[claim_token_idx:]

# 3. Average those scores
avg_claim_score = np.mean(claim_section_scores)

# 4. Label as lying or honest based on ACTUAL_CARDS vs CLAIM
is_lying = (actual_cards_text != claim_text)

# 5. Compare lying vs honest scores
```

**What we're measuring**: Average probe activation on tokens that comprise the claimed cards (e.g., "Ace, Ace, Ace, Ace")

**What we found**:
- Deception probe: lying=0.7455, honest=0.7418 (diff=0.0037)
- Hallucination probe: lying=0.3335, honest=0.3652 (diff=-0.0317, backwards)

---

## Why Probes Might Not Work

### 1. Training Distribution Mismatch
- **Deception probe**: Likely trained on conversational deception (lies about facts)
- **Hallucination probe**: Trained on factual errors where model doesn't know truth
- **Our task**: Strategic lying with full knowledge of truth

### 2. Context Awareness
When generating "CLAIM: Ace, Ace, Ace, Ace":
- Model has seen "ACTUAL_CARDS: King, King, King, King" in prompt
- Hidden states at generation time incorporate full prompt context
- Model "knows" it's lying - this is intentional deception, not hallucination

### 3. Probe Layer Selection
- Probes run on specific layer (likely layer 16 for 8B model)
- Deception might be encoded in different layers
- Or might not be localized to specific layers at all

### 4. Sigmoid + Bias Effect
- Bias shifts the entire distribution
- If bias is wrong, could compress separation to near-zero
- We don't know what bias values are being used

---

## What Actually Happens in the Code

1. **Player calls backend**: `backend.generate(messages)`
2. **Backend calls Modal**: `service.generate_with_probes.remote()`
3. **Modal service**:
   - Loads probe heads from disk
   - Registers forward hooks on transformer layers
   - Runs vLLM generation (prompt + generation)
   - Hooks capture hidden states for every token
   - Probes score each hidden state → raw logit
4. **Backend receives**:
   - Raw probe scores for all tokens
   - Applies sigmoid(score + bias)
   - Returns ProbeScores object
5. **Logger saves**:
   - prompt_tokens, tokens
   - prompt_token_scores, token_scores
   - To messages.jsonl
6. **Analysis reads**:
   - Loads messages.jsonl
   - Extracts CLAIM section scores
   - Compares lying vs honest

---

## Questions to Investigate

1. **What are the actual bias values?**
   - Check `self.probe_configs[probe_name].bias`
   - Might be compressing the range

2. **What layer are probes running on?**
   - Check `probe_layer` value
   - Try different layers?

3. **What are RAW scores before sigmoid?**
   - Currently we only see post-sigmoid scores
   - Raw scores might show more separation

4. **Are probes even loaded correctly?**
   - Verify probe files exist at volume paths
   - Check probe head architecture matches expected

5. **What was training data for these probes?**
   - Deception probe: what kind of lies?
   - Hallucination probe: what kind of errors?
