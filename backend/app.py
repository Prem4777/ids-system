from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from model_service import ModelService
from schemas import (
    BatchPredictRequest,
    BatchPredictResponse,
    AlertResponse,
    HealthResponse,
    MetadataResponse,
    MetricsResponse,
    PredictRequest,
    PredictionResult,
    SensorDataResponse,
    SensorRequest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = os.getenv("IDS_PIPELINE_PATH", "models/ton_iot/ton_iot_model_pipeline.joblib")
ENCODER_PATH = os.getenv("IDS_ENCODER_PATH", "models/ton_iot/ton_iot_label_encoder.joblib")
METADATA_PATH = os.getenv("IDS_METADATA_PATH", "models/ton_iot/ton_iot_metadata.json")

app = FastAPI(title="TON-IoT IDS Inference API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    service = ModelService(
        project_root=PROJECT_ROOT,
        pipeline_rel_path=PIPELINE_PATH,
        label_encoder_rel_path=ENCODER_PATH,
        metadata_rel_path=METADATA_PATH,
    )
except Exception as exc:
    service = None
    load_error = str(exc)
else:
    load_error = None


sensor_state: dict[str, object] = {
    "temperature": None,
    "humidity": None,
    "device_id": None,
    "sensor_timestamp": None,
    "received_at": None,
}


def _latest_alert() -> dict[str, object]:
    if service is None:
        return {
            "status": "offline",
            "attack_type": "unknown",
            "confidence": None,
            "detection_mode": None,
            "anomaly_reason": None,
            "timestamp": None,
        }

    events = service.recent_events(limit=1)
    if not events:
        return {
            "status": "normal",
            "attack_type": "normal",
            "confidence": None,
            "detection_mode": None,
            "anomaly_reason": None,
            "timestamp": None,
        }

    latest = events[0]
    label = str(latest.get("predicted_label", "normal"))
    is_attack = label.lower() != "normal"
    return {
        "status": "attack" if is_attack else "normal",
        "attack_type": label,
        "confidence": latest.get("confidence"),
        "detection_mode": latest.get("detection_mode"),
        "anomaly_reason": latest.get("anomaly_reason"),
        "timestamp": latest.get("timestamp"),
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    model_type = type(service.artifacts.pipeline).__name__ if service is not None else None
    status = "ok" if service is not None else f"error: {load_error}"
    return HealthResponse(status=status, model_loaded=service is not None, model_type=model_type)


@app.get("/metadata", response_model=MetadataResponse)
def metadata() -> MetadataResponse:
    if service is None:
        raise HTTPException(status_code=500, detail=f"Model service not available: {load_error}")
    return MetadataResponse(**service.metadata())


@app.get("/metrics", response_model=MetricsResponse)
def metrics() -> MetricsResponse:
    if service is None:
        raise HTTPException(status_code=500, detail=f"Model service not available: {load_error}")
    return MetricsResponse(**service.metrics())


@app.get("/events")
def events(limit: int = Query(default=100, ge=1, le=1000)) -> dict:
    if service is None:
        raise HTTPException(status_code=500, detail=f"Model service not available: {load_error}")
    return {"events": service.recent_events(limit=limit)}


@app.get("/get-alert", response_model=AlertResponse)
def get_alert() -> AlertResponse:
    return AlertResponse(**_latest_alert())


@app.post("/sensor", response_model=SensorDataResponse)
def post_sensor(payload: SensorRequest) -> SensorDataResponse:
    sensor_state["temperature"] = float(payload.temperature)
    sensor_state["humidity"] = float(payload.humidity)
    sensor_state["device_id"] = payload.device_id
    sensor_state["sensor_timestamp"] = float(payload.sensor_timestamp) if payload.sensor_timestamp is not None else time.time()
    sensor_state["received_at"] = time.time()
    return SensorDataResponse(**{**sensor_state, "status": "online"})


@app.get("/sensor-data", response_model=SensorDataResponse)
def get_sensor_data() -> SensorDataResponse:
    received_at = sensor_state.get("received_at")
    if not isinstance(received_at, (int, float)):
        return SensorDataResponse(**sensor_state, status="offline")

    age = time.time() - float(received_at)
    if age <= 10:
        status = "online"
    elif age <= 30:
        status = "stale"
    else:
        status = "offline"

    return SensorDataResponse(**sensor_state, status=status)


@app.post("/predict", response_model=PredictionResult)
def predict(payload: PredictRequest) -> PredictionResult:
    if service is None:
        raise HTTPException(status_code=500, detail=f"Model service not available: {load_error}")
    try:
        results = service.predict_many([payload.features], [payload.source])
        return PredictionResult(**results[0])
    except Exception as exc:
        service.error_count += 1
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/predict/batch", response_model=BatchPredictResponse)
def predict_batch(payload: BatchPredictRequest) -> BatchPredictResponse:
    if service is None:
        raise HTTPException(status_code=500, detail=f"Model service not available: {load_error}")
    if not payload.items:
        raise HTTPException(status_code=400, detail="No prediction items supplied")

    features = [item.features for item in payload.items]
    sources = [item.source for item in payload.items]

    try:
        results = service.predict_many(features, sources)
    except Exception as exc:
        service.error_count += 1
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    summary: dict[str, int] = {}
    for item in results:
        label = item["predicted_label"]
        summary[label] = summary.get(label, 0) + 1

    return BatchPredictResponse(
        results=[PredictionResult(**item) for item in results],
        summary=summary,
    )
