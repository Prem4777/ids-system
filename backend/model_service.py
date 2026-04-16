from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


@dataclass
class LoadedArtifacts:
    pipeline: Any
    label_encoder: Any | None
    metadata: dict[str, Any]


class ModelService:
    def __init__(
        self,
        project_root: Path,
        pipeline_rel_path: str = "models/ton_iot/ton_iot_model_pipeline.joblib",
        label_encoder_rel_path: str = "models/ton_iot/ton_iot_label_encoder.joblib",
        metadata_rel_path: str = "models/ton_iot/ton_iot_metadata.json",
    ) -> None:
        self.project_root = project_root
        self.pipeline_path = project_root / pipeline_rel_path
        self.label_encoder_path = project_root / label_encoder_rel_path
        self.metadata_path = project_root / metadata_rel_path

        self.artifacts = self._load_artifacts()
        self.feature_columns = self._resolve_feature_columns()
        self.classes = self._resolve_classes()

        self.total_requests = 0
        self.total_predictions = 0
        self.malicious_count = 0
        self.benign_count = 0
        self.error_count = 0
        self.total_latency_ms = 0.0
        self.events: deque[dict[str, Any]] = deque(maxlen=2000)
        self._profiler_rate_ema = 0.0
        self._profiler_packets_ema = 0.0
        self._profiler_bytes_ema = 0.0
        self._slow_abuse_windows = 0

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    def _apply_profiler_override(
        self,
        item: dict[str, Any],
        source: str | None,
        label: str,
        confidence: float | None,
    ) -> tuple[str, float | None, str, str | None, float, float, float, float]:
        packet_rate = self._to_float(item.get("_packet_rate"), 0.0)
        total_packets = self._to_float(item.get("_total_packets"), 0.0)
        total_bytes = self._to_float(item.get("_total_bytes"), 0.0)
        unique_dst_ports = self._to_float(item.get("_unique_dst_ports"), 0.0)
        syn_packets = self._to_float(item.get("_syn_packets"), 0.0)

        detection_mode = "ml"
        anomaly_reason: str | None = None

        if str(source or "").lower() != "packet-profiler":
            return label, confidence, detection_mode, anomaly_reason, packet_rate, total_packets, total_bytes, unique_dst_ports

        alpha = 0.2
        prev_rate_ema = self._profiler_rate_ema
        prev_packets_ema = self._profiler_packets_ema
        prev_bytes_ema = self._profiler_bytes_ema

        self._profiler_rate_ema = packet_rate if prev_rate_ema == 0 else (1 - alpha) * prev_rate_ema + alpha * packet_rate
        self._profiler_packets_ema = total_packets if prev_packets_ema == 0 else (1 - alpha) * prev_packets_ema + alpha * total_packets
        self._profiler_bytes_ema = total_bytes if prev_bytes_ema == 0 else (1 - alpha) * prev_bytes_ema + alpha * total_bytes

        # Hybrid trigger: classify realistic simulation profiles.
        scan_like = unique_dst_ports >= 8 and syn_packets >= 10 and packet_rate >= 15.0

        absolute_burst = packet_rate >= 120.0 or total_packets >= 350.0 or total_bytes >= 400000.0
        relative_spike = (
            prev_rate_ema > 0
            and packet_rate > (prev_rate_ema * 2.4)
            and total_packets > max(120.0, prev_packets_ema * 1.8)
        )

        # Slow abuse: sustained moderate abnormal load over several windows.
        slow_window = (
            packet_rate >= 28.0
            and packet_rate < 120.0
            and unique_dst_ports <= 5
            and total_packets >= 90.0
        )
        self._slow_abuse_windows = self._slow_abuse_windows + 1 if slow_window else 0
        slow_abuse = self._slow_abuse_windows >= 3

        if label.lower() in {"normal", "benign", "benigntraffic"}:
            if scan_like:
                label = "scanning"
                confidence = max(0.9, confidence or 0.0)
                detection_mode = "hybrid"
                anomaly_reason = "high-unique-dst-ports-syn-scan"
            elif absolute_burst or relative_spike:
                label = "dos"
                confidence = max(0.92, confidence or 0.0)
                detection_mode = "hybrid"
                anomaly_reason = "burst-rate-threshold" if absolute_burst else "rate-spike-vs-baseline"
            elif slow_abuse:
                label = "password"
                confidence = max(0.86, confidence or 0.0)
                detection_mode = "hybrid"
                anomaly_reason = "sustained-moderate-abuse-pattern"

        return label, confidence, detection_mode, anomaly_reason, packet_rate, total_packets, total_bytes, unique_dst_ports

    def _load_artifacts(self) -> LoadedArtifacts:
        if not self.pipeline_path.exists():
            raise FileNotFoundError(f"Model pipeline not found: {self.pipeline_path}")
        if not self.metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found: {self.metadata_path}")

        pipeline = joblib.load(self.pipeline_path)

        label_encoder = None
        if self.label_encoder_path.exists():
            try:
                label_encoder = joblib.load(self.label_encoder_path)
            except Exception:
                label_encoder = None

        with self.metadata_path.open("r", encoding="utf-8-sig") as f:
            metadata = json.load(f)

        return LoadedArtifacts(pipeline=pipeline, label_encoder=label_encoder, metadata=metadata)

    def _resolve_feature_columns(self) -> list[str]:
        features = self.artifacts.metadata.get("feature_columns")
        if isinstance(features, list) and features:
            return [str(x) for x in features]
        return []

    def _resolve_classes(self) -> list[str]:
        metadata_classes = self.artifacts.metadata.get("classes")
        if isinstance(metadata_classes, list) and metadata_classes:
            return [str(c) for c in metadata_classes]

        if hasattr(self.artifacts.pipeline, "classes_"):
            return [str(c) for c in self.artifacts.pipeline.classes_]

        if self.artifacts.label_encoder is not None and hasattr(self.artifacts.label_encoder, "classes_"):
            return [str(c) for c in self.artifacts.label_encoder.classes_]

        return []

    def _to_dataframe(self, feature_dicts: list[dict[str, Any]]) -> pd.DataFrame:
        df = pd.DataFrame(feature_dicts)
        if self.feature_columns:
            missing_cols = [col for col in self.feature_columns if col not in df.columns]
            for col in missing_cols:
                df[col] = np.nan
            df = df[self.feature_columns]
        return df

    def _decode_predictions(self, preds: np.ndarray) -> list[str]:
        if preds.dtype.kind in {"i", "u"} and self.artifacts.label_encoder is not None:
            try:
                decoded = self.artifacts.label_encoder.inverse_transform(preds)
                return [str(x) for x in decoded]
            except Exception:
                pass
        return [str(x) for x in preds]

    def _normalize_probabilities(self, row_probs: np.ndarray, classes: list[str]) -> dict[str, float]:
        return {cls: float(prob) for cls, prob in zip(classes, row_probs.tolist())}

    def predict_many(self, items: list[dict[str, Any]], sources: list[str | None] | None = None) -> list[dict[str, Any]]:
        start = time.perf_counter()
        self.total_requests += 1

        if not items:
            return []

        df = self._to_dataframe(items)
        raw_preds = self.artifacts.pipeline.predict(df)
        labels = self._decode_predictions(np.asarray(raw_preds))

        probas = None
        proba_classes: list[str] = []
        if hasattr(self.artifacts.pipeline, "predict_proba"):
            try:
                probas = self.artifacts.pipeline.predict_proba(df)
                proba_classes = [str(c) for c in getattr(self.artifacts.pipeline, "classes_", self.classes)]
                if self.artifacts.label_encoder is not None and getattr(self.artifacts.pipeline, "classes_", None) is not None:
                    try:
                        cls_arr = np.asarray(self.artifacts.pipeline.classes_)
                        if cls_arr.dtype.kind in {"i", "u"}:
                            proba_classes = [str(c) for c in self.artifacts.label_encoder.inverse_transform(cls_arr)]
                    except Exception:
                        pass
            except Exception:
                probas = None

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        per_item_latency = elapsed_ms / len(items)

        results: list[dict[str, Any]] = []
        for idx, label in enumerate(labels):
            probs = {}
            confidence = None
            if probas is not None:
                probs = self._normalize_probabilities(probas[idx], proba_classes)
                confidence = float(max(probs.values())) if probs else None

            source = sources[idx] if sources else None
            (
                label,
                confidence,
                detection_mode,
                anomaly_reason,
                packet_rate,
                total_packets,
                total_bytes,
                unique_dst_ports,
            ) = self._apply_profiler_override(items[idx], source, label, confidence)

            is_benign = label.lower() in {"normal", "benign", "benigntraffic"}
            if is_benign:
                self.benign_count += 1
            else:
                self.malicious_count += 1

            event = {
                "predicted_label": label,
                "confidence": confidence,
                "probabilities": probs,
                "latency_ms": round(per_item_latency, 3),
                "source": source,
                "detection_mode": detection_mode,
                "anomaly_reason": anomaly_reason,
                "packet_rate": packet_rate,
                "total_packets": total_packets,
                "total_bytes": total_bytes,
                "unique_dst_ports": unique_dst_ports,
                "timestamp": time.time(),
            }
            self.events.appendleft(event)
            results.append(event)

        self.total_predictions += len(items)
        self.total_latency_ms += elapsed_ms

        return results

    def metadata(self) -> dict[str, Any]:
        return {
            "target_column": self.artifacts.metadata.get("target_column"),
            "classes": self.classes,
            "feature_columns": self.feature_columns,
            "artifacts": {
                "pipeline": str(self.pipeline_path),
                "label_encoder": str(self.label_encoder_path),
                "metadata": str(self.metadata_path),
            },
        }

    def metrics(self) -> dict[str, Any]:
        avg_latency = self.total_latency_ms / self.total_predictions if self.total_predictions else 0.0
        return {
            "total_requests": self.total_requests,
            "total_predictions": self.total_predictions,
            "benign_count": self.benign_count,
            "malicious_count": self.malicious_count,
            "avg_latency_ms": round(avg_latency, 3),
            "error_count": self.error_count,
        }

    def recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return list(self.events)[: max(1, min(limit, 1000))]
