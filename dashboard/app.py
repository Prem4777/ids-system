from __future__ import annotations

import os
import socket
import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

DEFAULT_API_BASE_URL = os.getenv("IDS_API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="TON-IoT IDS Dashboard", layout="wide")
st.title("TON-IoT IDS Monitoring Dashboard")


def api_get(base_url: str, path: str) -> dict:
    response = requests.get(f"{base_url}{path}", timeout=20)
    response.raise_for_status()
    return response.json()


def discover_candidate_urls(current_url: str) -> list[str]:
    candidates: list[str] = []

    def add(url: str) -> None:
        cleaned = url.strip().rstrip("/")
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

    add(current_url)
    add("http://127.0.0.1:8000")
    add("http://localhost:8000")

    try:
        host_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        for ip in host_ips:
            if ip and not ip.startswith("127."):
                add(f"http://{ip}:8000")
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            add(f"http://{sock.getsockname()[0]}:8000")
    except OSError:
        pass

    return candidates


def probe_health(base_url: str) -> tuple[bool, str]:
    try:
        response = requests.get(f"{base_url}/health", timeout=2)
        response.raise_for_status()
        payload = response.json()
        if payload.get("model_loaded", False):
            return True, "ok"
        return True, str(payload.get("status", "reachable"))
    except requests.RequestException as exc:
        return False, str(exc)


st.sidebar.header("Live Controls")
if "api_base_url" not in st.session_state:
    st.session_state["api_base_url"] = DEFAULT_API_BASE_URL

api_base_url = st.sidebar.text_input("Backend API URL", value=st.session_state["api_base_url"]).strip().rstrip("/")
st.session_state["api_base_url"] = api_base_url

if st.sidebar.button("Auto-detect Live API"):
    matched_url = None
    for candidate in discover_candidate_urls(api_base_url):
        ok, _ = probe_health(candidate)
        if ok:
            matched_url = candidate
            break
    if matched_url:
        st.session_state["api_base_url"] = matched_url
        st.sidebar.success(f"Connected: {matched_url}")
        st.rerun()
    else:
        st.sidebar.error("No reachable backend found on common local/LAN addresses.")

if st.sidebar.button("Test Current API"):
    ok, detail = probe_health(api_base_url)
    if ok:
        st.sidebar.success(f"Reachable: {detail}")
    else:
        st.sidebar.error(f"Not reachable: {detail}")

auto_refresh = st.sidebar.toggle("Auto Refresh", value=True)
refresh_seconds = st.sidebar.slider("Refresh Interval (sec)", min_value=2, max_value=30, value=5, step=1)
st.caption(f"Backend API: {api_base_url}")

refresh_col1, refresh_col2 = st.columns([1, 3])
with refresh_col1:
    if st.button("Refresh Now"):
        st.session_state["force_refresh"] = True
with refresh_col2:
    st.caption(f"Read-only live dashboard. Auto refresh every {refresh_seconds}s.")

try:
    health = api_get(api_base_url, "/health")
    metrics = api_get(api_base_url, "/metrics")
    metadata = api_get(api_base_url, "/metadata")
    events_payload = api_get(api_base_url, "/events?limit=200")
    events = events_payload.get("events", [])
    alert = api_get(api_base_url, "/get-alert")
    sensor = api_get(api_base_url, "/sensor-data")
except requests.RequestException as exc:
    st.error(f"Cannot reach backend API at {api_base_url}: {exc}")
    st.stop()

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
