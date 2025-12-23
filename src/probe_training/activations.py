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
    verbose: bool = True
) -> Float[Tensor, "n_examples hidden_dim"]:
    """Extract activations from a list of texts at a specific layer.
    
    Extracts the last token activation for each text.
    
    Args:
        model: HuggingFace model
        tokenizer: HuggingFace tokenizer
        texts: List of text strings
        layer: Which layer to extract from (0-indexed)
        batch_size: Batch size for processing
        device: Device to run on
        verbose: Show progress bar
        
    Returns:
        Tensor of activations [n_examples, hidden_dim]
    """
    model.eval()
    model.to(device)
    
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
        
        # Extract activations from specified layer at last token position
        # hidden_states is a tuple of (n_layers+1) tensors
        # Each tensor is [batch, seq_len, hidden_dim]
        layer_activations = outputs.hidden_states[layer]  # [batch, seq_len, hidden_dim]
        
        # Get last token position for each sequence (accounting for padding)
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
    verbose: bool = True
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
        
    Returns:
        ActivationData with positive and negative activations
    """
    positive_texts = [pair.positive for pair in dataset_pairs]
    negative_texts = [pair.negative for pair in dataset_pairs]
    
    if verbose:
        print(f"Extracting activations for {len(dataset_pairs)} pairs at layer {layer}")
    
    positive_acts = extract_activations_from_text(
        model, tokenizer, positive_texts, layer, batch_size, device, verbose
    )
    negative_acts = extract_activations_from_text(
        model, tokenizer, negative_texts, layer, batch_size, device, verbose
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
