# Colab Workspace

This folder is meant to be copied to Google Drive and used from Google Colab.

Suggested layout:
- `notebooks/`: Colab notebooks (`*.ipynb`)
- `scripts/`: Python entrypoints (train/eval/export)
- `artifacts/`: model checkpoints and outputs (keep out of git)

Quick start (Colab):
1. Mount Google Drive
2. `cd` into the Drive copy of this `colab/` folder
3. `pip install -r requirements_colab.txt`
4. Run your notebook or scripts

Notes:
- Keep datasets and model checkpoints under `artifacts/` (ignored by `colab/.gitignore`).
- Keep small, stable config/code files committed in git.

