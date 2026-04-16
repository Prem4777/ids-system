# Backend Inference API

FastAPI backend for TON-IoT intrusion detection inference.

## Endpoints

- `GET /health` -> service and model load status
- `GET /metadata` -> classes and feature columns
- `POST /predict` -> single prediction
- `POST /predict/batch` -> batch prediction
- `GET /metrics` -> aggregate metrics
- `GET /events?limit=100` -> recent prediction events

## Local Run

```powershell
cd backend
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Recommended (explicit venv interpreter):

```powershell
cd "c:/Users/premg/OneDrive/Desktop/IDS project/backend"
& "c:/Users/premg/OneDrive/Desktop/IDS project/.venv/Scripts/python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000
```

## Environment Variables

- `IDS_PIPELINE_PATH` (default: `models/ton_iot/ton_iot_model_pipeline.joblib`)
- `IDS_ENCODER_PATH` (default: `models/ton_iot/ton_iot_label_encoder.joblib`)
- `IDS_METADATA_PATH` (default: `models/ton_iot/ton_iot_metadata.json`)

Paths are resolved relative to project root.
