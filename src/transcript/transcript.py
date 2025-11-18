"""Transcript data structures for storing conversation turns with probe annotations and metadata."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from ..backends.base import ProbeScores


@dataclass
class TokenData:
    """Data for a single token in a generation.
    
    Attributes:
        text: The token text
        logits: Top-k logits for this token position (token -> log probability)
        probe_scores: Per-token probe scores (probe_name -> score)
        metadata: Additional metadata for this token
    """
    text: str
    logits: Optional[Dict[str, float]] = None
    probe_scores: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TranscriptTurn:
    """A single turn in a conversation transcript.
    
    Represents one message in the conversation with all associated metadata,
    probe scores, logits, and token-level information.
    
    Attributes:
        role: The role of the speaker ('user', 'assistant', 'system')
        content: The text content of the message
        player_name: Optional player/agent name (e.g., 'deceiver', 'auditor')
        prompt: The prompt that generated this response (if role='assistant')
        tokens: List of token data with per-token annotations
        probe_scores: Aggregate probe scores for this turn
        metadata: Additional metadata (timestamps, config, etc.)
    """
    role: str
    content: str
    player_name: Optional[str] = None
    prompt: Optional[str] = None
    tokens: Optional[List[TokenData]] = None
    probe_scores: Optional[ProbeScores] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_generation_result(
        cls,
        role: str,
        content: str,
        result,  # GenerationResult from backend
        player_name: Optional[str] = None,
        prompt: Optional[str] = None,
        **metadata
    ) -> 'TranscriptTurn':
        """Create a TranscriptTurn from a backend GenerationResult.
        
        Args:
            role: The role of the speaker
            content: The text content
            result: GenerationResult object from backend.generate()
            player_name: Optional player/agent name
            prompt: The prompt that generated this response
            **metadata: Additional metadata to store
            
        Returns:
            TranscriptTurn with all data from the generation result
        """
        tokens = None
        if result.tokens:
            # Build TokenData objects from result
            token_list = []
            for i, token_text in enumerate(result.tokens):
                # Extract per-token data
                token_logits = None
                if result.top_k_logits and i < len(result.top_k_logits):
                    token_logits = result.top_k_logits[i]
                
                token_probe_scores = None
                if result.probe_scores and result.probe_scores.scores:
                    token_probe_scores = {}
                    for probe_name, score_data in result.probe_scores.scores.items():
                        if score_data.token_scores and i < len(score_data.token_scores):
                            token_probe_scores[probe_name] = score_data.token_scores[i]
                
                token_list.append(TokenData(
                    text=token_text,
                    logits=token_logits,
                    probe_scores=token_probe_scores
                ))
            tokens = token_list
        
        return cls(
            role=role,
            content=content,
            player_name=player_name,
            prompt=prompt,
            tokens=tokens,
            probe_scores=result.probe_scores,
            metadata=metadata
        )
    
    def get_token_text_list(self) -> List[str]:
        """Get list of token strings."""
        if not self.tokens:
            return []
        return [token.text for token in self.tokens]
    
    def get_probe_token_scores(self, probe_name: str) -> Optional[List[float]]:
        """Get per-token scores for a specific probe.
        
        Args:
            probe_name: Name of the probe
            
        Returns:
            List of per-token scores, or None if not available
        """
        if not self.tokens:
            return None
        
        scores = []
        for token in self.tokens:
            if token.probe_scores and probe_name in token.probe_scores:
                scores.append(token.probe_scores[probe_name])
            else:
                scores.append(None)
        
        # Return None if all scores are None
        if all(s is None for s in scores):
            return None
        return scores


@dataclass
class Transcript:
    """A complete conversation transcript with multiple turns.
    
    Manages a sequence of conversation turns with support for probe annotations,
    logits, and metadata across the entire conversation.
    
    Attributes:
        turns: List of conversation turns
        metadata: Global metadata for the entire transcript (experiment config, etc.)
    """
    turns: List[TranscriptTurn] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_turn(self, turn: TranscriptTurn) -> None:
        """Add a turn to the transcript."""
        self.turns.append(turn)
    
    def add_user_message(self, content: str, **metadata) -> None:
        """Add a simple user message."""
        self.turns.append(TranscriptTurn(
            role='user',
            content=content,
            metadata=metadata
        ))
    
    def add_assistant_message(
        self,
        content: str,
        prompt: Optional[str] = None,
        player_name: Optional[str] = None,
        **metadata
    ) -> None:
        """Add a simple assistant message without generation metadata."""
        self.turns.append(TranscriptTurn(
            role='assistant',
            content=content,
            player_name=player_name,
            prompt=prompt,
            metadata=metadata
        ))
    
    def add_generation(
        self,
        result,  # GenerationResult
        role: str = 'assistant',
        player_name: Optional[str] = None,
        prompt: Optional[str] = None,
        **metadata
    ) -> None:
        """Add a turn from a backend generation result.
        
        Args:
            result: GenerationResult from backend.generate()
            role: The role (default: 'assistant')
            player_name: Optional player/agent name
            prompt: The prompt used to generate this response
            **metadata: Additional metadata
        """
        turn = TranscriptTurn.from_generation_result(
            role=role,
            content=result.text,
            result=result,
            player_name=player_name,
            prompt=prompt,
            **metadata
        )
        self.turns.append(turn)
    
    def get_messages(self, include_system: bool = True) -> List[Dict[str, str]]:
        """Get transcript as list of message dicts (OpenAI format).
        
        Args:
            include_system: Whether to include system messages
            
        Returns:
            List of {'role': ..., 'content': ...} dicts
        """
        messages = []
        for turn in self.turns:
            if not include_system and turn.role == 'system':
                continue
            messages.append({
                'role': turn.role,
                'content': turn.content
            })
        return messages
    
    def get_turns_by_player(self, player_name: str) -> List[TranscriptTurn]:
        """Get all turns for a specific player."""
        return [turn for turn in self.turns if turn.player_name == player_name]
    
    def get_turns_with_probes(self) -> List[TranscriptTurn]:
        """Get all turns that have probe scores."""
        return [turn for turn in self.turns if turn.probe_scores is not None]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert transcript to dictionary for serialization.
        
        Returns:
            Dictionary representation of the transcript
        """
        return {
            'turns': [self._turn_to_dict(turn) for turn in self.turns],
            'metadata': self.metadata
        }
    
    def _turn_to_dict(self, turn: TranscriptTurn) -> Dict[str, Any]:
        """Convert a turn to dictionary."""
        turn_dict = {
            'role': turn.role,
            'content': turn.content,
            'metadata': turn.metadata
        }
        
        if turn.player_name:
            turn_dict['player_name'] = turn.player_name
        
        if turn.prompt:
            turn_dict['prompt'] = turn.prompt
        
        if turn.tokens:
            turn_dict['tokens'] = [
                {
                    'text': token.text,
                    'logits': token.logits,
                    'probe_scores': token.probe_scores,
                    'metadata': token.metadata
                }
                for token in turn.tokens
            ]
        
        if turn.probe_scores:
            # Convert ProbeScores to dict
            turn_dict['probe_scores'] = {
                'scores': {
                    probe_name: {
                        'aggregate_score': score_data.aggregate_score,
                        'token_scores': score_data.token_scores,
                        'phase_scores': score_data.phase_scores,
                        'metadata': score_data.metadata
                    }
                    for probe_name, score_data in turn.probe_scores.scores.items()
                }
            }
        
        return turn_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Transcript':
        """Create a Transcript from a dictionary.
        
        Args:
            data: Dictionary representation (from to_dict)
            
        Returns:
            Transcript object
        """
        from ..backends.base import ProbeScoreData
        
        turns = []
        for turn_data in data.get('turns', []):
            # Reconstruct tokens
            tokens = None
            if 'tokens' in turn_data:
                tokens = [
                    TokenData(
                        text=t['text'],
                        logits=t.get('logits'),
                        probe_scores=t.get('probe_scores'),
                        metadata=t.get('metadata', {})
                    )
                    for t in turn_data['tokens']
                ]
            
            # Reconstruct probe scores
            probe_scores = None
            if 'probe_scores' in turn_data:
                probe_scores = ProbeScores(
                    scores={
                        probe_name: ProbeScoreData(
                            aggregate_score=score_data['aggregate_score'],
                            token_scores=score_data.get('token_scores'),
                            phase_scores=score_data.get('phase_scores'),
                            metadata=score_data.get('metadata', {})
                        )
                        for probe_name, score_data in turn_data['probe_scores']['scores'].items()
                    }
                )
            
            turns.append(TranscriptTurn(
                role=turn_data['role'],
                content=turn_data['content'],
                player_name=turn_data.get('player_name'),
                prompt=turn_data.get('prompt'),
                tokens=tokens,
                probe_scores=probe_scores,
                metadata=turn_data.get('metadata', {})
            ))
        
        return cls(
            turns=turns,
            metadata=data.get('metadata', {})
        )
