# Probe Cache Directory

This directory contains locally cached probe weights downloaded from HuggingFace.

**All contents (except this README and .gitignore) are gitignored.**

## Structure

Each probe has its own subdirectory:

```
probes/
├── roleplaying-llama8b-linear-contrastive/
│   └── probe.pt
├── truthfulqa-llama70b-massmean/
│   └── probe.pt
└── ...
```

## Cache Management

- Probes are automatically downloaded on first use
- Checksums verify integrity before use
- If a cached probe is corrupted, it will be re-downloaded
- You can safely delete this directory - probes will be re-downloaded as needed

## Manual Cache Clear

```bash
# Clear all cached probes
rm -rf probes/*
# Keep .gitignore and README
git checkout probes/.gitignore probes/README.md
```
