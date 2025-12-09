#!/usr/bin/env python3
"""CLI for managing trained probes.

Commands:
    list        - List all registered probes
    info <name> - Show detailed information about a probe
    download <name> - Download a probe to local cache
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import directly from registry module to avoid heavy dependencies
from probe_training.registry import ProbeRegistry


def list_probes(args):
    """List all registered probes."""
    registry = ProbeRegistry()
    probe_names = registry.list_probes()

    if not probe_names:
        print("No probes registered yet.")
        return

    # Print header
    print()
    print(f"{'Probe Name':<60} {'Dataset':<15} {'Method':<20} {'Layer':<8} {'Accuracy':<12} {'Source'}")
    print("=" * 140)

    # Print each probe
    for name in probe_names:
        metadata = registry.get_metadata(name)
        accuracy = metadata.metrics.get('accuracy', 'N/A') if metadata.metrics else 'N/A'
        if isinstance(accuracy, float):
            accuracy = f"{accuracy:.2%}"

        # Determine source
        source = []
        if metadata.modal_path:
            source.append("Modal")
        if metadata.hf_repo:
            source.append("HF")
        source_str = ", ".join(source) if source else "Local"

        print(f"{name:<60} {metadata.dataset:<15} {metadata.method:<20} L{metadata.layer:<7} {str(accuracy):<12} {source_str}")

    print()
    print(f"Total: {len(probe_names)} probes")


def show_info(args):
    """Show detailed information about a probe."""
    registry = ProbeRegistry()

    try:
        metadata = registry.get_metadata(args.name)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    print(f"{'=' * 70}")
    print(f"Probe: {metadata.name}")
    print(f"{'=' * 70}")
    print()
    print(f"Dataset:      {metadata.dataset}")
    print(f"Model:        {metadata.model}")
    print(f"Method:       {metadata.method}")
    print(f"Layer:        {metadata.layer}")
    print(f"Created:      {metadata.created_at}")
    print(f"Checksum:     {metadata.checksum}")
    print()

    # Sources
    print("Sources:")
    if metadata.modal_path:
        print(f"  Modal:      {metadata.modal_path}")
    if metadata.hf_repo:
        print(f"  HuggingFace: {metadata.hf_repo}")
    if metadata.git_tag:
        print(f"  Git Tag:    {metadata.git_tag}")
    print()

    # Metrics
    if metadata.metrics:
        print("Metrics:")
        for key, value in metadata.metrics.items():
            if isinstance(value, float):
                print(f"  {key:20s}: {value:.4f}")
            else:
                print(f"  {key:20s}: {value}")
        print()

    # Check if cached locally
    probe_path = registry.cache_dir / metadata.name / "probe.pt"
    if probe_path.exists():
        print(f"✓ Cached locally at: {probe_path}")
    else:
        print(f"⚠ Not cached locally (will download on first use)")


def download_probe(args):
    """Download a probe to local cache."""
    registry = ProbeRegistry()

    try:
        print(f"Downloading probe: {args.name}")
        probe_path = registry.get_probe_path(args.name)
        print(f"✓ Probe downloaded to: {probe_path}")
    except ValueError as e:
        print(f"Error: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Manage trained probes",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List command
    list_parser = subparsers.add_parser("list", help="List all registered probes")
    list_parser.set_defaults(func=list_probes)

    # Info command
    info_parser = subparsers.add_parser("info", help="Show probe details")
    info_parser.add_argument("name", help="Probe name")
    info_parser.set_defaults(func=show_info)

    # Download command
    download_parser = subparsers.add_parser("download", help="Download probe to cache")
    download_parser.add_argument("name", help="Probe name")
    download_parser.set_defaults(func=download_probe)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
