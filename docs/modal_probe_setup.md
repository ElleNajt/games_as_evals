# Modal Probe Setup Guide

This guide explains how to upload probe files to Modal's volume storage for use with the 8B and 70B probe services.

## Prerequisites

1. **Modal account and authentication**
   ```bash
   # Install Modal
   pip install modal
   
   # Authenticate (one-time setup)
   modal setup
   ```

2. **Probe files locally**
   - The probes should be in the `probes/` directory
   - For 8B: `probes/deception_8b_layer12/` and `probes/hallucination_8b_layer30/`
   - For 70B: `probes/deception_70b_layer22/` and `probes/hallucination_70b_layer30/`

## Quick Start

If you've just cloned this repository and need to upload probes:

### Step 1: Verify probe files exist locally

```bash
# Check what probes you have
ls -lh probes/

# You should see directories like:
# - deception_8b_layer12/
# - hallucination_8b_layer30/
# - deception_70b_layer22/
# - hallucination_70b_layer30/
```

### Step 2: Upload probes to Modal volume

We provide scripts to upload the probes:

**For 70B probes:**
```bash
python -m modal run upload_70b_probes.py
```

**For 8B probes** (if not already uploaded):
```bash
python -m modal run upload_8b_probes.py
```

The upload scripts will:
1. Create a Modal container with the probe files
2. Copy them to the `unified-probe-models` volume
3. Commit the changes
4. Print confirmation when complete

Expected output:
```
✓ Initialized. View run at https://modal.com/apps/...
✓ Created objects.
Uploading /probes/deception_70b_layer22 to models/probes/deception_70b_layer22...
✓ Uploaded /probes/deception_70b_layer22
Uploading /probes/hallucination_70b_layer30 to models/probes/hallucination_70b_layer30...
✓ Uploaded /probes/hallucination_70b_layer30

✓ All 70B probes uploaded to Modal volume!
```

### Step 3: Verify probes are available

Run the integration tests to verify the probes work:

```bash
# Test 8B probes
python -m pytest src/tests/test_expensive_integration.py::TestBackendIntegration8B::test_8b_both_probes -v -m expensive

# Test 70B probes  
python -m pytest src/tests/test_expensive_integration.py::TestBackendIntegration70B::test_70b_both_probes -v -m expensive
```

If the tests pass, your probes are correctly uploaded and accessible!

## What's Happening Under the Hood

### Modal Volume Structure

Probes are stored in a Modal volume named `unified-probe-models` with this structure:

```
/volume/
└── models/
    └── probes/
        ├── deception_8b_layer12/
        │   └── probe_detector.pt
        ├── hallucination_8b_layer30/
        │   ├── probe_head.bin
        │   └── probe_config.json
        ├── deception_70b_layer22/
        │   └── probe_detector.pt
        └── hallucination_70b_layer30/
            ├── probe_head.bin
            └── probe_config.json
```

### Probe Formats

We support two probe formats:

1. **Apollo format** (deception probes)
   - Single file: `probe_detector.pt`
   - PyTorch model checkpoint

2. **Hallucination format** (from obalcells/hallucination-probes)
   - `probe_head.bin` - Probe weights
   - `probe_config.json` - Configuration (layer, model info)

The probe loading code automatically detects which format is present.

### How the Upload Script Works

The upload script (`upload_70b_probes.py`) does the following:

```python
# 1. Create Modal app and reference the volume
app = modal.App("upload-70b-probes")
volume = modal.Volume.from_name("unified-probe-models")

# 2. Create image with local probe files added
image = modal.Image.debian_slim().add_local_dir("probes", remote_path="/probes")

# 3. Run function in container that copies probes to volume
@app.function(volumes={"/volume": volume}, image=image)
def upload_probes():
    # Copy from /probes (in image) to /volume (volume mount)
    shutil.copytree("/probes/deception_70b_layer22", 
                    "/volume/models/probes/deception_70b_layer22")
    # ... repeat for each probe
    
    # Commit changes to persist
    volume.commit()
```

Key points:
- `add_local_dir()` copies local files into the container image
- The function runs in Modal's cloud and has access to both the image files and the volume
- `volume.commit()` is required to persist changes

## Troubleshooting

### "No valid probe found at /volume/models/probes/..."

This error means the probe wasn't uploaded or is in the wrong location.

**Solution:** Run the upload script again:
```bash
python -m modal run upload_70b_probes.py
```

### "Volume 'unified-probe-models' not found"

The volume needs to be created first. This should happen automatically when deploying the probe services, but you can create it manually:

```bash
python -c "import modal; modal.Volume.from_name('unified-probe-models', create_if_missing=True)"
```

### "Modal authentication failed"

You need to authenticate with Modal first:
```bash
modal setup
```

Follow the prompts to log in and create an API token.

### Upload script fails with "AttributeError: 'Image' object has no attribute 'copy_local_dir'"

Make sure you're using the correct method name `add_local_dir()` not `copy_local_dir()`:

```python
# ✓ Correct
image = modal.Image.debian_slim().add_local_dir("probes", remote_path="/probes")

# ✗ Wrong
image = modal.Image.debian_slim().copy_local_dir("probes", remote_path="/probes")
```

### Probe files are missing locally

If you don't have the probe files in `probes/`, you need to download them first:

**For 70B probes:**
```bash
python probes/setup_70b_probes.py
```

This will:
- Download hallucination_70b from HuggingFace (`obalcells/hallucination-probes`)
- Copy deception_70b from `external_repos/deception-detection`

**For 8B probes:**
Check if they're in the repository already, or refer to the probe acquisition documentation.

## Creating Your Own Upload Script

If you need to upload different probes or modify the upload process, here's a template:

```python
#!/usr/bin/env python3
"""Upload custom probes to Modal volume."""

import modal

app = modal.App("upload-custom-probes")
volume = modal.Volume.from_name("unified-probe-models", create_if_missing=False)

# Add local directory to image
image = modal.Image.debian_slim().add_local_dir("my_probes", remote_path="/probes")

@app.function(volumes={"/volume": volume}, image=image)
def upload_probes():
    import shutil
    from pathlib import Path
    
    # Define what to upload
    probes = [
        ("/probes/my_probe_name", "models/probes/my_probe_name"),
    ]
    
    for src, dst in probes:
        print(f"Uploading {src} to {dst}...")
        src_path = Path(src)
        dst_path = Path("/volume") / dst
        
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if dst_path.exists():
            shutil.rmtree(dst_path)
        shutil.copytree(src_path, dst_path)
        
        print(f"✓ Uploaded {src}")
    
    volume.commit()
    print("\n✓ All probes uploaded!")

@app.local_entrypoint()
def main():
    upload_probes.remote()
```

Run with:
```bash
python -m modal run your_upload_script.py
```

## Next Steps

After uploading probes:

1. **Deploy the probe services** (if not already deployed)
   ```bash
   modal deploy src/modal_deployments/unified_probe_service.py
   modal deploy src/modal_deployments/unified_probe_service_70b.py
   ```

2. **Run integration tests** to verify everything works
   ```bash
   pytest src/tests/test_expensive_integration.py -m expensive
   ```

3. **Use probes in your experiments**
   ```python
   from src.backends import create_backend
   
   backend = create_backend(
       "modal", 
       probes=["deception_8b", "hallucination_8b"],
       top_k_logits=10
   )
   
   result = backend.generate(
       messages=[{"role": "user", "content": "Tell me something."}],
       max_tokens=50
   )
   
   # Access probe scores
   print(result.probe_scores["deception_8b"].aggregate_score)
   ```

## Reference

- **Modal Documentation:** https://modal.com/docs
- **Probe Service Code:** `src/modal_deployments/unified_probe_service.py` and `unified_probe_service_70b.py`
- **Upload Scripts:** `upload_8b_probes.py`, `upload_70b_probes.py`
- **Integration Tests:** `src/tests/test_expensive_integration.py`
