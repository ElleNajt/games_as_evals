#!/usr/bin/env python3
"""Upload 8B probes to Modal volume."""

import modal

app = modal.App("upload-8b-probes")
volume = modal.Volume.from_name("unified-probe-models", create_if_missing=False)

# Create image with probes added
image = modal.Image.debian_slim().add_local_dir("probes", remote_path="/probes")


@app.function(volumes={"/volume": volume}, image=image)
def upload_probes():
    """Upload 8B probe directories to the volume."""
    import shutil
    from pathlib import Path

    # Source directories (added to image at /probes)
    probes_to_upload = [
        ("/probes/deception_8b_layer12", "models/probes/deception_8b_layer12"),
        ("/probes/hallucination_8b_layer30", "models/probes/hallucination_8b_layer30"),
    ]

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
    print("\n✓ All 8B probes uploaded to Modal volume!")


@app.local_entrypoint()
def main():
    """Run the upload."""
    upload_probes.remote()
