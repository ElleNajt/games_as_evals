#!/usr/bin/env python3
"""
Download and set up 70B probes for deception and hallucination detection.

This script:
1. Downloads hallucination 70B probe from HuggingFace (obalcells/hallucination-probes)
2. Copies deception 70B probe from external_repos/deception-detection
3. Organizes them into the correct directory structure
4. Optionally uploads them to Modal volume

Usage:
    python setup_70b_probes.py [--upload-to-modal]
"""

import os
import shutil
import subprocess
import argparse
from pathlib import Path
from huggingface_hub import hf_hub_download

# Paths
WORKSPACE = Path(__file__).parent.parent  # games_as_evals root directory
PROBES_DIR = WORKSPACE / "probes"
EXTERNAL_REPOS = WORKSPACE / "external_repos"

# Deception probe (local, from external_repos)
DECEPTION_SOURCE = EXTERNAL_REPOS / "deception-detection/example_results/roleplaying/detector.pt"
DECEPTION_TARGET = PROBES_DIR / "deception_70b_layer22"

# Hallucination probe (HuggingFace)
HF_REPO = "obalcells/hallucination-probes"
HF_PROBE_DIR = "llama3_3_70b_linear"  # Using the linear version
HALLUCINATION_TARGET = PROBES_DIR / "hallucination_70b_layer30"


def setup_deception_probe():
    """Copy deception 70B probe from external_repos."""
    print("=" * 70)
    print("Setting up Deception 70B Probe")
    print("=" * 70)
    
    if not DECEPTION_SOURCE.exists():
        raise FileNotFoundError(
            f"Deception probe source not found: {DECEPTION_SOURCE}\n"
            "Make sure external_repos/deception-detection submodule is initialized."
        )
    
    # Create target directory
    DECEPTION_TARGET.mkdir(parents=True, exist_ok=True)
    
    # Copy probe file
    target_file = DECEPTION_TARGET / "probe_detector.pt"
    shutil.copy2(DECEPTION_SOURCE, target_file)
    
    print(f"✓ Copied: {DECEPTION_SOURCE}")
    print(f"  → {target_file}")
    print(f"  Size: {target_file.stat().st_size / 1024:.1f} KB")
    print()


def setup_hallucination_probe():
    """Download hallucination 70B probe from HuggingFace."""
    print("=" * 70)
    print("Setting up Hallucination 70B Probe")
    print("=" * 70)
    
    # Create target directory
    HALLUCINATION_TARGET.mkdir(parents=True, exist_ok=True)
    
    # Files to download from HuggingFace
    files_to_download = [
        f"{HF_PROBE_DIR}/probe_head.bin",
        f"{HF_PROBE_DIR}/probe_config.json"
    ]
    
    print(f"Downloading from HuggingFace: {HF_REPO}")
    print(f"Directory: {HF_PROBE_DIR}")
    print()
    
    for file_path in files_to_download:
        print(f"Downloading {file_path}...")
        local_path = hf_hub_download(
            repo_id=HF_REPO,
            filename=file_path,
            local_dir=PROBES_DIR,
            local_dir_use_symlinks=False
        )
        
        # Move from nested HF directory structure to our target directory
        source = Path(local_path)
        target = HALLUCINATION_TARGET / source.name
        shutil.move(str(source), str(target))
        
        print(f"✓ Downloaded: {target.name}")
        print(f"  Size: {target.stat().st_size / 1024:.1f} KB")
    
    # Clean up the nested HF directory if it exists and is empty
    hf_nested_dir = PROBES_DIR / HF_PROBE_DIR
    if hf_nested_dir.exists() and not any(hf_nested_dir.iterdir()):
        hf_nested_dir.rmdir()
    
    print()


def upload_to_modal():
    """Upload 70B probes to Modal volume."""
    print("=" * 70)
    print("Uploading Probes to Modal Volume")
    print("=" * 70)
    
    # Check if modal CLI is available
    try:
        subprocess.run(["modal", "version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: Modal CLI not found or not configured.")
        print("Please run 'modal setup' first.")
        return False
    
    # Upload each probe directory to Modal volume
    for probe_dir in [DECEPTION_TARGET, HALLUCINATION_TARGET]:
        probe_name = probe_dir.name
        print(f"\nUploading {probe_name}...")
        
        # Modal volume put command
        # Format: modal volume put <volume-name> <local-path> <remote-path>
        cmd = [
            "modal", "volume", "put",
            "unified-probe-models",  # Volume name from unified_probe_service.py
            str(probe_dir),
            f"models/probes/{probe_name}"
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"✓ Uploaded {probe_name} to Modal volume 'unified-probe-models' at models/probes/{probe_name}")
            if result.stdout:
                print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"ERROR uploading {probe_name}:")
            print(e.stderr)
            return False
    
    print()
    print("✓✓✓ All probes uploaded to Modal! ✓✓✓")
    return True


def verify_setup():
    """Verify that all probe files are in place."""
    print("=" * 70)
    print("Verifying Probe Setup")
    print("=" * 70)
    
    all_good = True
    
    # Check deception probe
    deception_file = DECEPTION_TARGET / "probe_detector.pt"
    if deception_file.exists():
        size_kb = deception_file.stat().st_size / 1024
        print(f"✓ Deception 70B probe: {size_kb:.1f} KB")
    else:
        print(f"✗ Deception 70B probe NOT FOUND: {deception_file}")
        all_good = False
    
    # Check hallucination probe
    hallucination_head = HALLUCINATION_TARGET / "probe_head.bin"
    hallucination_config = HALLUCINATION_TARGET / "probe_config.json"
    
    if hallucination_head.exists() and hallucination_config.exists():
        size_kb = hallucination_head.stat().st_size / 1024
        print(f"✓ Hallucination 70B probe: {size_kb:.1f} KB")
    else:
        if not hallucination_head.exists():
            print(f"✗ Hallucination probe head NOT FOUND: {hallucination_head}")
        if not hallucination_config.exists():
            print(f"✗ Hallucination probe config NOT FOUND: {hallucination_config}")
        all_good = False
    
    print()
    
    if all_good:
        print("✓✓✓ All 70B probes successfully set up! ✓✓✓")
    else:
        print("✗✗✗ Some probes are missing ✗✗✗")
    
    return all_good


def main():
    parser = argparse.ArgumentParser(description="Set up 70B probes for deception and hallucination detection")
    parser.add_argument(
        "--upload-to-modal",
        action="store_true",
        help="Upload probes to Modal volume after downloading"
    )
    args = parser.parse_args()
    
    print("=" * 70)
    print("70B Probe Setup Script")
    print("=" * 70)
    print()
    
    try:
        # Download/copy probes
        setup_deception_probe()
        setup_hallucination_probe()
        
        # Verify
        if not verify_setup():
            print("\nERROR: Probe setup incomplete!")
            return 1
        
        # Upload to Modal if requested
        if args.upload_to_modal:
            if not upload_to_modal():
                print("\nERROR: Modal upload failed!")
                return 1
        else:
            print("Skipping Modal upload (use --upload-to-modal to enable)")
            print()
        
        print("=" * 70)
        print("SETUP COMPLETE!")
        print("=" * 70)
        print()
        print("Next steps:")
        if not args.upload_to_modal:
            print("  1. Upload to Modal: python setup_70b_probes.py --upload-to-modal")
            print("  2. Test with: python -m pytest src/tests/test_probes_direct.py::TestProbesDirect70B")
        else:
            print("  1. Test with: python -m pytest src/tests/test_probes_direct.py::TestProbesDirect70B")
        print()
        
        return 0
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
