# Model Layout Guide

This project expects model artifacts to exist locally under the `models/` directory, but these files are not stored in git.

## Required Files

1. `models/stage1_model.pkl`

- Stage 1 classifier artifact.

2. `models/stage2_model.pkl`

- Stage 2 classifier artifact.

3. `models/le_stage2.pkl`

- Label encoder used by Stage 2 outputs.

4. `models/ton_iot/TON_IOT_INTRUSION_DETECTION_MODEL.joblib`

- TON_IoT main model artifact.

5. `models/ton_iot/ton_iot_model_pipeline.joblib`

- TON_IoT pipeline artifact.

6. `models/ton_iot/ton_iot_label_encoder.joblib`

- TON_IoT label encoder artifact.

## Optional Metadata Files

- `models/ton_iot/TON_IOT_INTRUSION_DETECTION_MODEL_METADATA.json`
- `models/ton_iot/ton_iot_metadata.json`

## Folder Placement Summary

- Put `stage1_model.pkl`, `stage2_model.pkl`, and `le_stage2.pkl` directly inside `models/`.
- Put TON_IoT artifacts inside `models/ton_iot/`.

## Notes

- Keep file names exactly as shown above.
- If your source files have different names, rename them to match before running backend or notebooks.
- If you train models locally, export artifacts to these exact paths.
