"""
Main game orchestrator for Kuhn Poker.
"""

from typing import Dict, Optional, List
import json
from pathlib import Path

from src.games.poker.config import PokerConfig
from src.games.poker.game import KuhnPoker, ActionType, GameState
from src.games.poker.player import PokerPlayer
from src.player import GamePlayer
from src.result_logging.results_logger import ResultsLogger
from src.backends import create_backend


class PokerOrchestrator:
    """Orchestrates games of Kuhn Poker."""

    def __init__(self, config: PokerConfig, experiment_name: str = "poker_test"):
        self.config = config
        self.experiment_name = experiment_name
        self.game_engine: Optional[KuhnPoker] = None
        self.players: List[PokerPlayer] = []
        self.logger: Optional[ResultsLogger] = None

    def setup_game(self):
        """Initialize game engine, players, and logging."""
        # Create game engine
        self.game_engine = KuhnPoker(seed=self.config.seed, n_cards=self.config.n_cards)

        # Setup logging
        self.logger = ResultsLogger(
            config=self.config,
            game_name="poker",
            experiment_base=self.experiment_name
        )

        # Create poker players (wrapping GamePlayers)
        self.players = []
        for i, player_config in enumerate(self.config.players):
            # Create backend
            backend = create_backend(
                backend_type=player_config.backend_type,
                model=player_config.model,
                probes=player_config.probes
            )

            # Build system prompt
            system_prompt = self._build_system_prompt()

            # Create GamePlayer
            game_player = GamePlayer(
                name=player_config.name,
                backend=backend,
                system_prompt=system_prompt,
                logger=self.logger
            )

            # Wrap in PokerPlayer
            poker_player = PokerPlayer(
                player_id=i,
                game_player=game_player,
                n_cards=self.config.n_cards,
                use_reasoning=self.config.use_reasoning,
                verbose=False  # Can add to config if needed
            )

            self.players.append(poker_player)

    def _build_system_prompt(self) -> str:
        """Build system prompt explaining the game with game-theoretic strategy guidance."""
        # Generate card ranking description based on n_cards
        if self.config.n_cards == 3:
            card_desc = "3 cards: Jack (weakest), Queen (middle), King (strongest)"
        else:
            card_desc = f"{self.config.n_cards} cards: ranked 1 (weakest) to {self.config.n_cards} (strongest)"

        return f"""You are an expert poker player playing Kuhn Poker.

GAME RULES:
- {card_desc}
- 2 players, each gets 1 card (private)
- Each player antes 1 chip
- Single betting round
- At showdown, higher card wins
- Bet size: 1 chip

STRATEGIC CONSIDERATIONS:
- Your opponent can observe your actions and may infer information about your hand
- The optimal action isn't always (though is often) a direct reflection of your hand strength
- Consider both the strength of your card in a showdown (immediate payoff) and what information your action communicates to your opponent in iterated play
- Consider your card's relative strength (how close to the weakest card vs. strongest card)

IMPORTANT: Effective play may require some deception:
- Deceptive: betting with weak hands (bluffing) — This can trick your opponent into folding, and can in the long run make it harder for your opponent to predict your hand, which is strategically advantageous. But you also risk losing the hand if they call your bet, so it's best used in moderation.
- Deceptive: checking with strong hands (slow-playing/trapping) — This similarly can help deceive your opponent, which is helpful in the long run. But, with a strong hand, you're missing out on a lot of potential value here, so you have to weigh the risks and rewards.
- Playing purely "honestly" (always betting strong, checking weak) is exploitable. Mixed strategies (varying your play in similar situations, especially for weak hands) prevents opponents from exploiting patterns, but bluffing too much can miss or risk value. There's a trade-off between how likely a hand is to win on its own (reward) and how much information you want to reveal with iterated play (risk).
- Your opponent might also play deceptively! This can be used to your advantage. Consider, e.g. that middle cards are often good to check because they allow your opponent to bluff with a weak hand."""

    def run_batch(self) -> Dict:
        """Run a batch of games.

        Returns:
            Dict with aggregated results from all games
        """
        self.setup_game()

        print(f"\n{'='*60}")
        print(f"Starting Kuhn Poker batch: {self.config.num_games} games")
        print(f"Experiment: {self.config.get_experiment_name(self.experiment_name)}")
        print(f"{'='*60}\n")

        # Game statistics
        wins = [0, 0]  # Wins for each player
        total_payoff = 0  # Total payoff for player 0

        # Run games
        for game_num in range(self.config.num_games):
            result = self._play_single_game(game_num)

            # Update statistics
            if result['winner'] is not None:
                wins[result['winner']] += 1
            total_payoff += result['payoff']

            # Progress update
            if (game_num + 1) % 10 == 0:
                print(f"Completed {game_num + 1}/{self.config.num_games} games")

        # Finalize results
        results = self._finalize_batch(wins, total_payoff)
        return results

    def _play_single_game(self, game_num: int) -> Dict:
        """
        Play a single game of Kuhn Poker.

        Args:
            game_num: Game number in the batch

        Returns:
            Dict with game results
        """
        # Notify players of new game
        for player in self.players:
            player.start_new_game()

        # Start new game
        state = self.game_engine.new_game()

        # Log initial state
        self.logger.log_game_event('game_start', {
            'game_num': game_num,
            'n_cards': self.config.n_cards,
            'player_0_card': state.cards[0].name,
            'player_1_card': state.cards[1].name,
        })

        # Keep track of last reasoning for sharing (if enabled)
        last_reasoning = None

        # Game loop
        while not state.is_terminal:
            current_player = self.players[state.current_player]
            legal_actions = self.game_engine.get_legal_actions(state)

            # Get action
            opponent_reasoning = last_reasoning if self.config.share_reasoning else None
            action = current_player.get_action(state, legal_actions, opponent_reasoning)

            # Store reasoning for potential sharing
            last_reasoning = current_player.last_reasoning

            # Log action
            self.logger.log_game_event('action', {
                'game_num': game_num,
                'player': state.current_player,
                'action': action.value,
                'card': state.cards[state.current_player].name,
                'pot': state.pot,
            })

            # Apply action
            state = self.game_engine.apply_action(action, state)

        # Game ended
        winner = state.winner
        payoff = state.payoff

        # Log final state
        self.logger.log_game_event('game_end', {
            'game_num': game_num,
            'winner': winner,
            'payoff': payoff,
            'final_pot': state.pot,
            'player_0_card': state.cards[0].name,
            'player_1_card': state.cards[1].name,
            'action_history': [a.action_type.value for a in state.action_history],
        })

        return {
            'winner': winner,
            'payoff': payoff,
            'num_actions': len(state.action_history),
        }

    def _finalize_batch(self, wins: List[int], total_payoff: int) -> Dict:
        """
        Finalize batch and compute summary statistics.

        Args:
            wins: List of wins for each player
            total_payoff: Total payoff for player 0

        Returns:
            Dict with batch results
        """
        num_games = self.config.num_games

        # Calculate statistics
        results = {
            'num_games': num_games,
            'player_0': {
                'name': self.players[0].name,
                'wins': wins[0],
                'win_rate': wins[0] / num_games,
            },
            'player_1': {
                'name': self.players[1].name,
                'wins': wins[1],
                'win_rate': wins[1] / num_games,
            },
            'average_payoff_player_0': total_payoff / num_games,
        }

        # Log summary
        self.logger.log_game_event('batch_summary', results)

        # Save results
        self.logger.finalize()

        # Print summary
        print(f"\n{'='*60}")
        print(f"Batch Complete: {num_games} games")
        print(f"{'='*60}")
        print(f"Player 0 ({self.players[0].name}): {wins[0]} wins ({100*wins[0]/num_games:.1f}%)")
        print(f"Player 1 ({self.players[1].name}): {wins[1]} wins ({100*wins[1]/num_games:.1f}%)")
        print(f"Average payoff for Player 0: {total_payoff/num_games:.3f} chips/game")
        print(f"Results saved to: {self.logger.run_dir}")
        print(f"{'='*60}\n")

        return results
