"""Test HTML visualization generation using mocked game results.

This test loads real game_results.json files from previous TTL runs
and verifies that visualization generation works correctly without
running the full game orchestration.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.backends.base import ProbeScores, ProbeScoreData
from src.config.game_config import GameConfig
from src.result_logging.results_logger import ResultsLogger


class TestVisualizationWithMockedResults:
    """Test visualization generation using saved game results."""
    
    @pytest.fixture
    def sample_game_results(self):
        """Load sample game results from saved JSON file."""
        # Use the game results file mentioned by the user
        results_file = Path('results/ttl/ttl_viz_fix_test_2e7dc46_40a36f7_dirty/game1/game_results.json')
        
        if not results_file.exists():
            # If that specific file doesn't exist, find any game_results.json
            results_files = list(Path('results/ttl').glob('*/game*/game_results.json'))
            if results_files:
                results_file = results_files[0]
            else:
                pytest.skip("No game_results.json files found in results/ttl/")
        
        with open(results_file) as f:
            return json.load(f)
    
    def test_visualization_with_real_game_data(self, sample_game_results):
        """Test HTML generation with real game data from saved results.
        
        This test saves HTML to results/test_visualizations/ for inspection.
        """
        # Extract data from the saved game results
        assert 'deceiver_generation' in sample_game_results, "Missing deceiver_generation field"
        
        dec_gen = sample_game_results['deceiver_generation']
        
        # Extract tokens and probe scores
        tokens = dec_gen.get('generated_tokens', [])
        probe_token_scores = dec_gen.get('probe_token_scores', {})
        
        assert len(tokens) > 0, "No tokens in saved results"
        assert len(probe_token_scores) > 0, "No probe scores in saved results"
        
        # Create ProbeScores object from the saved data
        probe_scores_dict = {}
        for probe_name, token_scores in probe_token_scores.items():
            # Calculate aggregate score (mean of token scores)
            aggregate = sum(token_scores) / len(token_scores) if token_scores else 0.0
            
            probe_scores_dict[probe_name] = ProbeScoreData(
                aggregate_score=aggregate,
                token_scores=token_scores
            )
        
        probe_scores = ProbeScores(scores=probe_scores_dict)
        
        # Use a persistent directory for test output so you can inspect the HTML
        tmpdir = 'results/test_visualizations'
        Path(tmpdir).mkdir(parents=True, exist_ok=True)
        
        config = GameConfig(output_dir=tmpdir)
        logger = ResultsLogger(
            config=config,
            game_name='ttl_test',
            experiment_base='mocked_viz',
            game_id=1
        )
        
        # Log the message with probe data
        logger.log_message(
            player_name='deceiver',
            role='assistant',
            prompt='Generate statements',
            response=dec_gen.get('generated_text', ''),
            tokens=tokens,
            probe_scores=probe_scores
        )
        
        # Generate consolidated HTML
        html_file = logger.generate_consolidated_visualization()
        
        # Verify HTML was created
        assert html_file is not None, "HTML file was not generated"
        assert html_file.exists(), f"HTML file does not exist: {html_file}"
        
        # Read and verify HTML content
        with open(html_file) as f:
            html_content = f.read()
        
        # Verify key HTML elements
        assert '<!DOCTYPE html>' in html_content, "Missing HTML DOCTYPE"
        assert 'Probe Activations' in html_content, "Missing title"
        
        # Verify all probes are present
        for probe_name in probe_token_scores.keys():
            assert probe_name in html_content, f"Probe {probe_name} not found in HTML"
        
        # Verify multi-probe features
        assert 'input[type="radio"]' in html_content, "Missing radio buttons for probe selection"
        assert 'updateColors()' in html_content, "Missing JavaScript recoloring function"
        
        # Verify data attributes for all probes
        for probe_name in probe_token_scores.keys():
            assert f'data-{probe_name}' in html_content, f"Missing data attributes for {probe_name}"
        
        # Verify tooltip features
        assert '.token .tooltip' in html_content, "Missing tooltip CSS"
        assert 'position: relative' in html_content, "Missing relative positioning"
        assert 'position: absolute' in html_content, "Missing absolute positioning"
        assert '.token:hover .tooltip' in html_content, "Missing hover trigger"
        
        # Verify some tokens are present (check first few)
        for token in tokens[:5]:
            # Token might have Ġ replaced with space
            display_token = token.replace('Ġ', ' ')
            assert display_token in html_content or token in html_content, \
                f"Token {token} not found in HTML"
    
    def test_visualization_handles_g_character(self, sample_game_results):
        """Test that Ġ character is properly handled in visualization."""
        dec_gen = sample_game_results['deceiver_generation']
        tokens = dec_gen.get('generated_tokens', [])
        probe_token_scores = dec_gen.get('probe_token_scores', {})
        
        # Find tokens with Ġ character
        g_tokens = [t for t in tokens if 'Ġ' in t]
        
        if not g_tokens:
            pytest.skip("No tokens with Ġ character in this dataset")
        
        # Create minimal probe scores
        probe_scores = ProbeScores(
            scores={
                list(probe_token_scores.keys())[0]: ProbeScoreData(
                    aggregate_score=0.5,
                    token_scores=[0.5] * len(tokens)
                )
            }
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name='ttl_test',
                experiment_base='g_char_test',
                game_id=1
            )
            
            logger.log_message(
                player_name='test',
                role='assistant',
                prompt='Test',
                response=' '.join(tokens),
                tokens=tokens,
                probe_scores=probe_scores
            )
            
            html_file = logger.generate_consolidated_visualization()
            assert html_file is not None
            
            with open(html_file) as f:
                content = f.read()
            
            # Check that Ġ tokens are handled
            for g_token in g_tokens:
                space_token = g_token.replace('Ġ', ' ')
                # Either the space version should be in main display
                # OR original should be preserved in tooltip
                assert space_token in content or f'Token: {g_token}' in content, \
                    f"Token {g_token} not properly handled"
    
    def test_visualization_multiple_probes(self, sample_game_results):
        """Test that visualization correctly handles multiple probes."""
        dec_gen = sample_game_results['deceiver_generation']
        probe_token_scores = dec_gen.get('probe_token_scores', {})
        
        if len(probe_token_scores) < 2:
            pytest.skip("This dataset only has one probe")
        
        tokens = dec_gen.get('generated_tokens', [])
        
        # Create ProbeScores with multiple probes
        probe_scores_dict = {}
        for probe_name, token_scores in probe_token_scores.items():
            aggregate = sum(token_scores) / len(token_scores) if token_scores else 0.0
            probe_scores_dict[probe_name] = ProbeScoreData(
                aggregate_score=aggregate,
                token_scores=token_scores
            )
        
        probe_scores = ProbeScores(scores=probe_scores_dict)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name='ttl_test',
                experiment_base='multi_probe_test',
                game_id=1
            )
            
            logger.log_message(
                player_name='test',
                role='assistant',
                prompt='Test',
                response=' '.join(tokens),
                tokens=tokens,
                probe_scores=probe_scores
            )
            
            html_file = logger.generate_consolidated_visualization()
            assert html_file is not None
            
            with open(html_file) as f:
                content = f.read()
            
            # Verify radio button for each probe
            probe_names = list(probe_token_scores.keys())
            for probe_name in probe_names:
                assert f'value="{probe_name}"' in content, \
                    f"Missing radio button for {probe_name}"
                assert f'data-{probe_name}' in content, \
                    f"Missing data attributes for {probe_name}"
            
            # Verify tooltips show all probe scores
            for probe_name in probe_names:
                # Tooltip should have probe name
                assert f'{probe_name}:' in content, \
                    f"Probe {probe_name} not in tooltip"
    
    def test_visualization_token_count_matches(self, sample_game_results):
        """Test that probe scores match token count."""
        dec_gen = sample_game_results['deceiver_generation']
        tokens = dec_gen.get('generated_tokens', [])
        probe_token_scores = dec_gen.get('probe_token_scores', {})
        
        # Verify each probe has scores for all tokens
        for probe_name, scores in probe_token_scores.items():
            assert len(scores) == len(tokens), \
                f"{probe_name} has {len(scores)} scores but {len(tokens)} tokens"
        
        # Create ProbeScores and verify it works in visualization
        probe_scores_dict = {}
        for probe_name, token_scores in probe_token_scores.items():
            aggregate = sum(token_scores) / len(token_scores)
            probe_scores_dict[probe_name] = ProbeScoreData(
                aggregate_score=aggregate,
                token_scores=token_scores
            )
        
        probe_scores = ProbeScores(scores=probe_scores_dict)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config = GameConfig(output_dir=tmpdir)
            logger = ResultsLogger(
                config=config,
                game_name='ttl_test',
                experiment_base='count_test',
                game_id=1
            )
            
            logger.log_message(
                player_name='test',
                role='assistant',
                prompt='Test',
                response=' '.join(tokens),
                tokens=tokens,
                probe_scores=probe_scores
            )
            
            html_file = logger.generate_consolidated_visualization()
            assert html_file is not None, "Failed to generate HTML"
            
            # If we got here, the visualization was created successfully
            # which means token counts matched
    
    def test_visualization_with_statements(self, sample_game_results):
        """Test visualization using the actual statements from the game."""
        statements = sample_game_results.get('statements', [])
        
        if not statements:
            pytest.skip("No statements in this dataset")
        
        dec_gen = sample_game_results['deceiver_generation']
        
        # Verify the statements are in the generated text
        generated_text = dec_gen.get('generated_text', '')
        
        for i, statement in enumerate(statements, 1):
            assert statement in generated_text, \
                f"Statement {i} not found in generated text"


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])
