#!/usr/bin/env python3
"""Upload 70B probes to Modal volume.

Usage:
    # Upload only roleplaying probes (default)
    python -m modal run upload_70b_probes.py

    # Upload all probes including instructive pairs (if available)
    python -m modal run upload_70b_probes.py::upload_probes_with_instructive

    # Check what probes are available
    python -m modal run upload_70b_probes.py::list_available_probes
"""

import modal

app = modal.App("upload-70b-probes")
volume = modal.Volume.from_name("unified-probe-models", create_if_missing=False)

# Create image with probes added
image = modal.Image.debian_slim().add_local_dir("probes", remote_path="/probes")

@app.function(volumes={"/volume": volume}, image=image)
def upload_probes(include_instructive_pairs=False):
    """Upload 70B probe directories to the volume.

    Args:
        include_instructive_pairs: If True, also upload instructive pairs probe if available
    """
    import shutil
    from pathlib import Path

    # Source directories (added to image at /probes)
    # Always upload roleplaying probes (deception, hallucination)
    probes_to_upload = [
        ("/probes/deception_70b_layer22", "models/probes/deception_70b_layer22"),
        ("/probes/hallucination_70b_layer30", "models/probes/hallucination_70b_layer30"),
    ]

    # Optionally add instructive pairs probe
    if include_instructive_pairs:
        # Check for 70B instructive pairs probe (if you train one)
        instructive_70b_candidates = [
            "/probes/instructive_pairs_70b_layer40",  # Potential 70B location
            "/probes/instructive_pairs_70b_layer22",  # Alternative layer
        ]

        found_70b = False
        for candidate_path in instructive_70b_candidates:
            if Path(candidate_path).exists():
                probe_name = Path(candidate_path).name
                probes_to_upload.append(
                    (candidate_path, f"models/probes/{probe_name}")
                )
                print(f"✓ Found 70B instructive pairs probe at {candidate_path}")
                found_70b = True
                break

        if not found_70b:
            # Fall back to 8B version if no 70B version exists
            instructive_8b_path = "/probes/instructive_pairs_8b_layer20"
            if Path(instructive_8b_path).exists():
                print("⚠️  No 70B instructive pairs probe found, using 8B version")
                print("   Note: The 8B probe won't work with 70B models directly")
                print("   Consider training a 70B version using probe_training_service.py")
                probes_to_upload.append(
                    (instructive_8b_path, "models/probes/instructive_pairs_8b_layer20")
                )
            else:
                print("❌ No instructive pairs probe found (neither 70B nor 8B)")
    
    for local_path, remote_path in probes_to_upload:
        print(f"Uploading {local_path} to {remote_path}...")
        
        # Copy files from image to volume mount
        src = Path(local_path)
        dst = Path("/volume") / remote_path
        
        # Create parent directory
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy directory
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        
        print(f"✓ Uploaded {local_path}")
    
    # Commit the volume
    volume.commit()
    print(f"\n✓ {len(probes_to_upload)} probe(s) uploaded to Modal volume!")

@app.function(volumes={"/volume": volume}, image=image)
def upload_probes_with_instructive():
    """Upload all probes including instructive pairs."""
    upload_probes(include_instructive_pairs=True)

@app.function(image=image)
def list_available_probes():
    """List all available probe directories in the local probes/ folder."""
    from pathlib import Path

    probes_dir = Path("/probes")
    print("=" * 60)
    print("Available Probes in /probes directory:")
    print("=" * 60)

    # Check for 70B probes
    print("\n70B Probes:")
    print("-" * 30)
    probes_70b = [
        "deception_70b_layer22",
        "hallucination_70b_layer30",
        "instructive_pairs_70b_layer40",  # Potential future probe
        "instructive_pairs_70b_layer22",  # Alternative location
    ]

    for probe_name in probes_70b:
        probe_path = probes_dir / probe_name
        if probe_path.exists():
            # Check what files are in the probe directory
            files = list(probe_path.iterdir())
            file_names = [f.name for f in files]
            print(f"✓ {probe_name}")
            print(f"  Files: {', '.join(file_names)}")
        else:
            print(f"✗ {probe_name} (not found)")

    # Check for 8B probes that could be referenced
    print("\n8B Probes (for reference):")
    print("-" * 30)
    probes_8b = [
        "deception_8b_layer12",
        "hallucination_8b_layer30",
        "instructive_pairs_8b_layer20",
        "instructive_pairs_8b_layer20_l2_5",
    ]

    for probe_name in probes_8b:
        probe_path = probes_dir / probe_name
        if probe_path.exists():
            files = list(probe_path.iterdir())
            file_names = [f.name for f in files]
            print(f"✓ {probe_name}")
            print(f"  Files: {', '.join(file_names)}")
        else:
            print(f"✗ {probe_name} (not found)")

    print("\n" + "=" * 60)

@app.local_entrypoint()
def main():
    """Run the default upload (roleplaying probes only)."""
    print("Uploading default probes (deception and hallucination)...")
    print("To include instructive pairs, use:")
    print("  python -m modal run upload_70b_probes.py::upload_probes_with_instructive")
    print()
    upload_probes.remote(include_instructive_pairs=False)
