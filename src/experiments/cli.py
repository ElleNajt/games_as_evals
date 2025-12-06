"""Common CLI argument parser for experiments."""

import argparse
from typing import Callable, Optional


def create_base_parser(description: str) -> argparse.ArgumentParser:
    """Create base argument parser with common options.

    Args:
        description: Description of the experiment

    Returns:
        ArgumentParser with common arguments added
    """
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Common arguments shared across all experiments
    parser.add_argument(
        "--num-rounds",
        type=int,
        default=10,
        help="Number of game rounds to run (default: 10)",
    )

    parser.add_argument(
        "--experiment-name",
        type=str,
        default=None,
        help="Custom experiment name (default: auto-generated from config)",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    return parser


def add_ttl_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add TTL-specific arguments to parser.

    Args:
        parser: Base argument parser

    Returns:
        Parser with TTL-specific arguments added
    """
    ttl_group = parser.add_argument_group("TTL-specific options")

    ttl_group.add_argument(
        "--use-real-facts",
        action="store_true",
        default=True,
        help="Use real-world facts for statements (default: True)",
    )

    ttl_group.add_argument(
        "--use-fictional-facts",
        action="store_true",
        help="Use fictional facts instead of real-world facts",
    )

    return parser


def add_werewolf_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Add Werewolf-specific arguments to parser.

    Args:
        parser: Base argument parser

    Returns:
        Parser with Werewolf-specific arguments added
    """
    werewolf_group = parser.add_argument_group("Werewolf-specific options")

    werewolf_group.add_argument(
        "--num-players",
        type=int,
        default=5,
        help="Number of players in the game (default: 5)",
    )

    werewolf_group.add_argument(
        "--num-werewolves",
        type=int,
        default=2,
        help="Number of werewolves in the game (default: 2)",
    )

    werewolf_group.add_argument(
        "--max-turns",
        type=int,
        default=10,
        help="Maximum number of turns per game (default: 10)",
    )

    return parser


def create_ttl_parser(description: str) -> argparse.ArgumentParser:
    """Create parser for TTL experiments.

    Args:
        description: Experiment description

    Returns:
        Configured ArgumentParser for TTL experiments
    """
    parser = create_base_parser(description)
    parser = add_ttl_arguments(parser)
    return parser


def create_werewolf_parser(description: str) -> argparse.ArgumentParser:
    """Create parser for Werewolf experiments.

    Args:
        description: Experiment description

    Returns:
        Configured ArgumentParser for Werewolf experiments
    """
    parser = create_base_parser(description)
    parser = add_werewolf_arguments(parser)
    return parser
