from __future__ import annotations

import os
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_BASE_URL = os.getenv("IDS_API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="TON-IoT IDS Dashboard", layout="wide")
st.title("TON-IoT IDS Monitoring Dashboard")
st.caption(f"Backend API: {API_BASE_URL}")


def api_get(path: str) -> dict:
    response = requests.get(f"{API_BASE_URL}{path}", timeout=20)
    response.raise_for_status()
    return response.json()


st.sidebar.header("Live Controls")
auto_refresh = st.sidebar.toggle("Auto Refresh", value=True)
refresh_seconds = st.sidebar.slider("Refresh Interval (sec)", min_value=2, max_value=30, value=5, step=1)

refresh_col1, refresh_col2 = st.columns([1, 3])
with refresh_col1:
    if st.button("Refresh Now"):
        st.session_state["force_refresh"] = True
with refresh_col2:
    st.caption(f"Read-only live dashboard. Auto refresh every {refresh_seconds}s.")

health = api_get("/health")
metrics = api_get("/metrics")
metadata = api_get("/metadata")
events_payload = api_get("/events?limit=200")
events = events_payload.get("events", [])
alert = api_get("/get-alert")
sensor = api_get("/sensor-data")

if not health.get("model_loaded", False):
    st.error(f"Model not loaded: {health.get('status')}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Requests", metrics.get("total_requests", 0))
c2.metric("Total Predictions", metrics.get("total_predictions", 0))
c3.metric("Malicious", metrics.get("malicious_count", 0))
c4.metric("Avg Latency (ms)", metrics.get("avg_latency_ms", 0.0))

st.divider()

st.subheader("IoT Sensor Status")
s1, s2, s3, s4 = st.columns(4)
sensor_status = str(sensor.get("status", "offline")).upper()
s1.metric("Sensor Link", sensor_status)

temperature = sensor.get("temperature")
humidity = sensor.get("humidity")
received_at = sensor.get("received_at")
s2.metric("Temperature (C)", f"{float(temperature):.2f}" if isinstance(temperature, (float, int)) else "n/a")
s3.metric("Humidity (%)", f"{float(humidity):.2f}" if isinstance(humidity, (float, int)) else "n/a")
s4.metric(
    "Sensor Updated",
    datetime.fromtimestamp(received_at).strftime("%Y-%m-%d %H:%M:%S") if isinstance(received_at, (float, int)) else "n/a",
)

if sensor_status == "OFFLINE":
    st.info("Sensor not connected yet. Phase 3 endpoint is ready and waiting for IoT device data.")
elif sensor_status == "STALE":
    st.warning("Sensor data is stale. Check device power/network and publish interval.")
else:
    st.success("Sensor data stream is active.")

st.divider()

status_col1, status_col2, status_col3, status_col4 = st.columns(4)
status_col1.metric("Model Type", health.get("model_type", "unknown"))
status_col2.metric("Classes", len(metadata.get("classes", [])))
status_col3.metric("Feature Columns", len(metadata.get("feature_columns", [])))
status_col4.metric("Error Count", metrics.get("error_count", 0))

st.subheader("Latest Detection")
if events:
    latest = events[0]
    is_attack = str(alert.get("status", "normal")).lower() == "attack"
    l1, l2, l3, l4, l5 = st.columns(5)
    l1.metric("Current Status", "ATTACK" if is_attack else "NORMAL")
    l2.metric("Attack Type", str(alert.get("attack_type", latest.get("predicted_label", "unknown"))))
    conf = alert.get("confidence", latest.get("confidence"))
    l3.metric("Confidence", f"{conf:.4f}" if isinstance(conf, (float, int)) else "n/a")
    ts = alert.get("timestamp", latest.get("timestamp"))
    human_ts = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if isinstance(ts, (float, int)) else "n/a"
    l4.metric("Last Update", human_ts)
    l5.metric("Detection Mode", str(alert.get("detection_mode", latest.get("detection_mode", "ml"))))

    anomaly_reason = alert.get("anomaly_reason", latest.get("anomaly_reason"))
    if anomaly_reason:
        st.warning(f"Hybrid alert trigger: {anomaly_reason}")

    t1, t2, t3 = st.columns(3)
    t1.metric("Packet Rate (/s)", f"{float(latest.get('packet_rate', 0.0)):.2f}")
    t2.metric("Window Packets", int(float(latest.get("total_packets", 0.0))))
    t3.metric("Window Bytes", int(float(latest.get("total_bytes", 0.0))))

    if is_attack:
        st.error("Active anomaly detected. Review source traffic and event timeline below.")
    else:
        st.success("Traffic currently appears stable.")
else:
    st.info("No prediction events yet. Start profiler or call /predict to populate live details.")

st.subheader("Live Events")
if events:
    events_df = pd.DataFrame(events)
    events_df["timestamp"] = events_df["timestamp"].apply(lambda x: datetime.fromtimestamp(x))
    st.dataframe(events_df, use_container_width=True)

    if "packet_rate" in events_df.columns:
        trend_df = events_df[["timestamp", "packet_rate"]].copy().dropna()
        if not trend_df.empty:
            trend_df = trend_df.sort_values("timestamp")
            trend_fig = px.line(trend_df, x="timestamp", y="packet_rate", title="Packet Rate Trend")
            st.plotly_chart(trend_fig, use_container_width=True)

    cls_counts = events_df["predicted_label"].value_counts().reset_index()
    cls_counts.columns = ["label", "count"]
    fig = px.bar(cls_counts, x="label", y="count", title="Recent Predictions by Class")
    st.plotly_chart(fig, use_container_width=True)

if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
