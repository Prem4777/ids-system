# Dataset Layout Guide

This project expects CSV datasets to exist locally under the `data/` directory, but these files are not stored in git.

## Required Files

1. `data/train.csv`

- Main training dataset used for model training experiments.

2. `data/test.csv`

- Test dataset used for evaluation and inference checks.

3. `data/validation.csv`

- Validation dataset used for model selection and sanity checks.

4. `data/ton_iot/train_test_network.csv`

- TON_IoT network dataset variant used by TON_IoT-focused notebooks/pipelines.

## Folder Placement Summary

- Put `train.csv`, `test.csv`, and `validation.csv` directly inside `data/`.
- Put `train_test_network.csv` inside `data/ton_iot/`.

## Notes

- Keep file names exactly as shown above.
- If your source files have different names, rename them to match before running notebooks or services.
- After placing files, verify paths before training/inference runs.
