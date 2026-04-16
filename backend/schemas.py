from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PredictionItem(BaseModel):
    features: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None


class PredictRequest(PredictionItem):
    pass


class BatchPredictRequest(BaseModel):
    items: list[PredictionItem] = Field(default_factory=list)


class PredictionResult(BaseModel):
    predicted_label: str
    confidence: float | None = None
    probabilities: dict[str, float] = Field(default_factory=dict)
    latency_ms: float
    source: str | None = None
    detection_mode: str | None = None
    anomaly_reason: str | None = None
    packet_rate: float | None = None
    total_packets: float | None = None
    total_bytes: float | None = None
    unique_dst_ports: float | None = None


class BatchPredictResponse(BaseModel):
    results: list[PredictionResult]
    summary: dict[str, int]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_type: str | None = None


class MetricsResponse(BaseModel):
    total_requests: int
    total_predictions: int
    benign_count: int
    malicious_count: int
    avg_latency_ms: float
    error_count: int


class MetadataResponse(BaseModel):
    target_column: str | None
    classes: list[str]
    feature_columns: list[str]
    artifacts: dict[str, str]


class SensorRequest(BaseModel):
    temperature: float
    humidity: float
    device_id: str | None = None
    sensor_timestamp: float | None = None


class SensorDataResponse(BaseModel):
    temperature: float | None = None
    humidity: float | None = None
    device_id: str | None = None
    sensor_timestamp: float | None = None
    received_at: float | None = None
    status: str = "offline"


class AlertResponse(BaseModel):
    status: str
    attack_type: str
    confidence: float | None = None
    detection_mode: str | None = None
    anomaly_reason: str | None = None
    timestamp: float | None = None
