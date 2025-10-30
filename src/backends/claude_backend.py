"""Claude CLI backend implementation."""

import subprocess
import json
from typing import List, Dict
from .base import LLMBackend, GenerationResult


class ClaudeBackend(LLMBackend):
    """
    Backend using Claude CLI (claude -p).
    
    Does NOT support probes or logits - only returns text.
    Uses --system-prompt flag to ensure isolated system prompts.
    """
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """
        Generate using Claude CLI.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens (not enforced by CLI, truncated after)
            temperature: Temperature (not supported by CLI, ignored)
            
        Returns:
            GenerationResult with only text populated
        """
        # Extract system and user prompts
        system_prompt = ""
        user_prompt = ""
        
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] == "user":
                user_prompt = msg["content"]
        
        # Build command
        cmd = ["claude", "-p"]
        
        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])
        
        cmd.append(user_prompt)
        
        # Execute
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Claude command failed: {result.stderr}")
        
        response = result.stdout.strip()
        
        # Remove path warnings if present
        lines = response.split('\n')
        response = '\n'.join([
            line for line in lines 
            if 'was not found' not in line
        ]).strip()
        
        return GenerationResult(
            text=response,
            tokens=None,
            top_k_logits=None,
            probe_scores=None
        )
    
    @property
    def supports_probes(self) -> bool:
        return False
    
    @property
    def supports_logits(self) -> bool:
        return False
