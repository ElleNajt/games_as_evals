"""Activation extraction utilities for probe training."""

import torch
from typing import List, Tuple, Optional
from dataclasses import dataclass
from transformers import AutoTokenizer, AutoModelForCausalLM
from jaxtyping import Float
from torch import Tensor
from tqdm import trange

from .dataset import ContrastivePair


@dataclass
class ActivationData:
    """Holds activations extracted from a model.
    
    Attributes:
        positive_acts: Activations for positive (truthful) examples [n_examples, hidden_dim]
        negative_acts: Activations for negative (deceptive) examples [n_examples, hidden_dim]
        layer: Which layer these activations came from
    """
    positive_acts: Float[Tensor, "n_examples hidden_dim"]
    negative_acts: Float[Tensor, "n_examples hidden_dim"]
    layer: int


def extract_activations_from_text(
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    texts: List[str],
    layer: int,
    batch_size: int = 8,
    device: str = "cuda",
    verbose: bool = True,
    use_all_tokens: bool = True,
    exclude_last_n_tokens: int = 0
) -> Float[Tensor, "n_examples hidden_dim"]:
    """Extract activations from a list of texts at a specific layer.

    Args:
        model: HuggingFace model
        tokenizer: HuggingFace tokenizer
        texts: List of text strings
        layer: Which layer to extract from (0-indexed)
        batch_size: Batch size for processing
        device: Device to run on
        verbose: Show progress bar
        use_all_tokens: If True, returns mean of all token activations (Apollo's approach).
                       If False, returns only the last token activation.
        exclude_last_n_tokens: Number of tokens to exclude from the end (for REPE dataset).
                              Only used when use_all_tokens=True.

    Returns:
        Tensor of activations [n_examples, hidden_dim]
    """
    model.eval()
    # Don't call model.to(device) when using device_map="auto"
    # The model is already placed correctly by accelerate

    all_activations = []
    
    for i in trange(0, len(texts), batch_size, disable=not verbose, desc="Extracting activations"):
        batch_texts = texts[i:i + batch_size]
        
        # Tokenize
        encoded = tokenizer(
            batch_texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512
        )
        
        input_ids = encoded["input_ids"].to(device)
        attention_mask = encoded["attention_mask"].to(device)
        
        # Forward pass with activation extraction
        with torch.no_grad():
            outputs = model(
                input_ids,
                attention_mask=attention_mask,
                output_hidden_states=True,
                use_cache=False
            )
        
        # Extract activations from specified layer
        # hidden_states is a tuple of (n_layers+1) tensors
        # Each tensor is [batch, seq_len, hidden_dim]
        layer_activations = outputs.hidden_states[layer]  # [batch, seq_len, hidden_dim]

        if use_all_tokens:
            # Apollo's approach: Take mean of all non-padded tokens
            # Create mask for real tokens (non-padding)
            mask = attention_mask.clone().unsqueeze(-1)  # [batch, seq_len, 1]

            # Exclude last N tokens if specified (for REPE dataset)
            if exclude_last_n_tokens > 0:
                # Find the position of the last real token for each sequence
                seq_lengths = attention_mask.sum(dim=1)  # [batch]
                for j in range(len(seq_lengths)):
                    last_pos = seq_lengths[j].item()
                    # Zero out the last N tokens in the mask
                    start_exclude = max(0, last_pos - exclude_last_n_tokens)
                    mask[j, start_exclude:last_pos, :] = 0

            # Mask out padding tokens and excluded tokens, then compute mean
            masked_activations = layer_activations * mask  # [batch, seq_len, hidden_dim]
            token_counts = mask.sum(dim=1)  # [batch, hidden_dim]
            # Avoid division by zero
            token_counts = torch.clamp(token_counts, min=1.0)
            mean_activations = masked_activations.sum(dim=1) / token_counts  # [batch, hidden_dim]

            all_activations.append(mean_activations.cpu())
        else:
            # Original approach: Get last token position for each sequence (accounting for padding)
            last_token_positions = attention_mask.sum(dim=1) - 1  # [batch]

            # Extract last token activations
            batch_acts = []
            for j, pos in enumerate(last_token_positions):
                batch_acts.append(layer_activations[j, pos, :])

            all_activations.append(torch.stack(batch_acts).cpu())
    
    return torch.cat(all_activations, dim=0)


def extract_contrastive_activations(
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    dataset_pairs: List[ContrastivePair],
    layer: int,
    batch_size: int = 8,
    device: str = "cuda",
    verbose: bool = True,
    use_all_tokens: bool = True,
    exclude_last_n_tokens: int = 0
) -> ActivationData:
    """Extract activations for contrastive pairs.

    Args:
        model: HuggingFace model
        tokenizer: HuggingFace tokenizer
        dataset_pairs: List of contrastive pairs
        layer: Which layer to extract from
        batch_size: Batch size for processing
        device: Device to run on
        verbose: Show progress bar
        use_all_tokens: If True, uses mean of all tokens (Apollo's approach).
                       If False, uses only last token.
        exclude_last_n_tokens: Number of tokens to exclude from the end (for REPE dataset).

    Returns:
        ActivationData with positive and negative activations
    """
    positive_texts = [pair.positive for pair in dataset_pairs]
    negative_texts = [pair.negative for pair in dataset_pairs]
    
    if verbose:
        print(f"Extracting activations for {len(dataset_pairs)} pairs at layer {layer}")
    
    positive_acts = extract_activations_from_text(
        model, tokenizer, positive_texts, layer, batch_size, device, verbose,
        use_all_tokens, exclude_last_n_tokens
    )
    negative_acts = extract_activations_from_text(
        model, tokenizer, negative_texts, layer, batch_size, device, verbose,
        use_all_tokens, exclude_last_n_tokens
    )
    
    return ActivationData(
        positive_acts=positive_acts,
        negative_acts=negative_acts,
        layer=layer
    )


def load_model_and_tokenizer(model_name: str, device: str = "cuda"):
    """Load a HuggingFace model and tokenizer.
    
    Args:
        model_name: Model identifier (e.g., "meta-llama/Meta-Llama-3.1-8B-Instruct")
        device: Device to load on
        
    Returns:
        (model, tokenizer) tuple
    """
    print(f"Loading model: {model_name}")
    
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        device_map="auto" if device == "cuda" else None
    )
    
    return model, tokenizer
