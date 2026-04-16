from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import requests
from scapy.all import AsyncSniffer, DNS, DNSQR, IP, Raw, TCP, UDP

# Load the expected feature columns from the model metadata to ensure compatibility.
def load_feature_columns(metadata_path: Path) -> list[str]:
    with metadata_path.open("r", encoding="utf-8-sig") as f:
        metadata = json.load(f)
    columns = metadata.get("feature_columns", [])
    return [str(col) for col in columns]

# Build a safe default payload with all expected columns, using zeros or placeholders.
def base_payload(feature_columns: list[str]) -> dict[str, Any]:
    # Build a safe default row that matches the trained pipeline schema.
    numeric_defaults = {
        "src_port": 0,
        "dst_port": 0,
        "duration": 0.0,
        "src_bytes": 0.0,
        "dst_bytes": 0.0,
        "missed_bytes": 0.0,
        "src_pkts": 0.0,
        "src_ip_bytes": 0.0,
        "dst_pkts": 0.0,
        "dst_ip_bytes": 0.0,
        "dns_qclass": 0.0,
        "dns_qtype": 0.0,
        "dns_rcode": 0.0,
        "dns_AA": 0.0,
        "dns_RD": 0.0,
        "dns_RA": 0.0,
        "dns_rejected": 0.0,
        "http_trans_depth": 0.0,
        "http_request_body_len": 0.0,
        "http_response_body_len": 0.0,
        "http_status_code": 0.0,
    }

    row: dict[str, Any] = {}
    for col in feature_columns:
        if col in numeric_defaults:
            row[col] = numeric_defaults[col]
        else:
            row[col] = "-"
    return row

# Build window-level features from captured packets, ensuring all expected columns are present.
def build_window_features(packets: list[Any], window_seconds: float, feature_columns: list[str]) -> dict[str, Any]:
    row = base_payload(feature_columns)

    total_packets = len(packets)
    total_bytes = float(sum(len(pkt) for pkt in packets))
    avg_packet_size = (total_bytes / total_packets) if total_packets else 0.0
    packet_rate = (total_packets / window_seconds) if window_seconds > 0 else 0.0

    proto_counter: Counter[str] = Counter()
    src_port_counter: Counter[int] = Counter()
    dst_port_counter: Counter[int] = Counter()
    flow_pkt_count: defaultdict[tuple[str, str], int] = defaultdict(int)
    flow_bytes: defaultdict[tuple[str, str], float] = defaultdict(float)
    tcp_flag_counter: Counter[str] = Counter()
    http_method_counter: Counter[str] = Counter()
    http_status_counter: Counter[int] = Counter()
    dns_query_counter: Counter[str] = Counter()
    dns_qclass_counter: Counter[float] = Counter()
    dns_qtype_counter: Counter[float] = Counter()
    dns_rcode_counter: Counter[float] = Counter()

    request_body_bytes = 0.0
    response_body_bytes = 0.0
    http_uri = "-"
    http_version = "-"
    dns_AA = 0.0
    dns_RD = 0.0
    dns_RA = 0.0
    dns_rejected = 0.0
    ssl_seen = False

    for pkt in packets:
        pkt_len = float(len(pkt))

        if IP in pkt:
            ip_layer = pkt[IP]
            src_ip = str(ip_layer.src)
            dst_ip = str(ip_layer.dst)
            flow_key = (src_ip, dst_ip)
            flow_pkt_count[flow_key] += 1
            flow_bytes[flow_key] += pkt_len

        if TCP in pkt:
            proto_counter["tcp"] += 1
            tcp_layer = pkt[TCP]
            if tcp_layer.sport:
                src_port_counter[int(tcp_layer.sport)] += 1
            if tcp_layer.dport:
                dst_port_counter[int(tcp_layer.dport)] += 1

            # Track common TCP state signals.
            flags = str(tcp_layer.flags)
            if "S" in flags:
                tcp_flag_counter["syn"] += 1
            if "A" in flags:
                tcp_flag_counter["ack"] += 1
            if "R" in flags:
                tcp_flag_counter["rst"] += 1
            if "F" in flags:
                tcp_flag_counter["fin"] += 1

            if int(tcp_layer.sport) == 443 or int(tcp_layer.dport) == 443:
                ssl_seen = True

            # Parse basic HTTP request/response signals when raw payload is present.
            if Raw in pkt:
                payload = bytes(pkt[Raw].load)
                try:
                    text = payload.decode("latin-1", errors="ignore")
                except Exception:
                    text = ""
                first_line = text.split("\r\n", 1)[0] if text else ""

                if first_line.startswith(("GET ", "POST ", "PUT ", "DELETE ", "PATCH ", "HEAD ", "OPTIONS ")):
                    parts = first_line.split(" ")
                    if len(parts) >= 3:
                        method = parts[0].upper()
                        http_method_counter[method] += 1
                        http_uri = parts[1] if parts[1] else "-"
                        http_version = parts[2] if parts[2] else "-"
                    request_body_bytes += float(len(payload))
                elif first_line.startswith("HTTP/"):
                    parts = first_line.split(" ")
                    if len(parts) >= 2 and parts[1].isdigit():
                        http_status_counter[int(parts[1])] += 1
                        http_version = parts[0]
                    response_body_bytes += float(len(payload))

        elif UDP in pkt:
            proto_counter["udp"] += 1
            udp_layer = pkt[UDP]
            if udp_layer.sport:
                src_port_counter[int(udp_layer.sport)] += 1
            if udp_layer.dport:
                dst_port_counter[int(udp_layer.dport)] += 1

        else:
            proto_counter["other"] += 1

        if DNS in pkt:
            dns_layer = pkt[DNS]
            dns_AA = max(dns_AA, float(getattr(dns_layer, "aa", 0)))
            dns_RD = max(dns_RD, float(getattr(dns_layer, "rd", 0)))
            dns_RA = max(dns_RA, float(getattr(dns_layer, "ra", 0)))
            dns_rcode_counter[float(getattr(dns_layer, "rcode", 0))] += 1
            if getattr(dns_layer, "rcode", 0) != 0:
                dns_rejected = 1.0

            if DNSQR in pkt:
                dns_q = pkt[DNSQR]
                qname = str(getattr(dns_q, "qname", b"-")).strip("b'")
                if qname:
                    dns_query_counter[qname] += 1
                dns_qclass_counter[float(getattr(dns_q, "qclass", 0))] += 1
                dns_qtype_counter[float(getattr(dns_q, "qtype", 0))] += 1

    dominant_proto = proto_counter.most_common(1)[0][0] if proto_counter else "tcp"
    src_port = src_port_counter.most_common(1)[0][0] if src_port_counter else 0
    dst_port = dst_port_counter.most_common(1)[0][0] if dst_port_counter else 0

    # Infer service label from dominant destination port.
    service_map = {
        53: "dns",
        80: "http",
        443: "ssl",
        5000: "http",
        8000: "http",
    }
    service = service_map.get(int(dst_port), "-")

    # Use the dominant flow to split directional packet and byte counts.
    if flow_pkt_count:
        (src_ip, dst_ip), src_pkts = max(flow_pkt_count.items(), key=lambda x: x[1])
        src_pkts = float(src_pkts)
        src_ip_bytes = float(flow_bytes[(src_ip, dst_ip)])
        dst_pkts = float(flow_pkt_count.get((dst_ip, src_ip), 0))
        dst_ip_bytes = float(flow_bytes.get((dst_ip, src_ip), 0.0))
    else:
        src_pkts = float(total_packets)
        dst_pkts = 0.0
        src_ip_bytes = float(total_bytes)
        dst_ip_bytes = 0.0

    # Approximate Zeek-style connection state from observed TCP flags.
    if tcp_flag_counter["rst"] > 0:
        conn_state = "REJ"
    elif tcp_flag_counter["syn"] > 0 and tcp_flag_counter["ack"] == 0:
        conn_state = "S0"
    elif tcp_flag_counter["syn"] > 0 and tcp_flag_counter["ack"] > 0:
        conn_state = "SF"
    else:
        conn_state = "OTH"

    # Map profiler metrics into model-compatible columns.
    row["src_port"] = float(src_port)
    row["dst_port"] = float(dst_port)
    row["proto"] = dominant_proto
    row["service"] = service
    row["duration"] = float(window_seconds)
    row["src_bytes"] = float(src_ip_bytes)
    row["dst_bytes"] = float(dst_ip_bytes)
    row["conn_state"] = conn_state
    row["missed_bytes"] = 0.0
    row["src_pkts"] = float(src_pkts)
    row["src_ip_bytes"] = float(src_ip_bytes)
    row["dst_pkts"] = float(dst_pkts)
    row["dst_ip_bytes"] = float(dst_ip_bytes)

    row["dns_query"] = dns_query_counter.most_common(1)[0][0] if dns_query_counter else "-"
    row["dns_qclass"] = dns_qclass_counter.most_common(1)[0][0] if dns_qclass_counter else 0.0
    row["dns_qtype"] = dns_qtype_counter.most_common(1)[0][0] if dns_qtype_counter else 0.0
    row["dns_rcode"] = dns_rcode_counter.most_common(1)[0][0] if dns_rcode_counter else 0.0
    row["dns_AA"] = float(dns_AA)
    row["dns_RD"] = float(dns_RD)
    row["dns_RA"] = float(dns_RA)
    row["dns_rejected"] = float(dns_rejected)

    row["ssl_version"] = "TLS" if ssl_seen else "-"
    row["ssl_cipher"] = "-"
    row["ssl_resumed"] = "F"
    row["ssl_established"] = "T" if ssl_seen else "F"
    row["ssl_subject"] = "-"
    row["ssl_issuer"] = "-"

    row["http_trans_depth"] = float(max(1, sum(http_method_counter.values()))) if http_method_counter else 0.0
    row["http_method"] = http_method_counter.most_common(1)[0][0] if http_method_counter else "-"
    row["http_uri"] = http_uri
    row["http_version"] = http_version
    row["http_request_body_len"] = float(request_body_bytes)
    row["http_response_body_len"] = float(response_body_bytes)
    row["http_status_code"] = float(http_status_counter.most_common(1)[0][0]) if http_status_counter else 0.0
    row["http_user_agent"] = "-"
    row["http_orig_mime_types"] = "-"
    row["http_resp_mime_types"] = "-"
    row["weird_name"] = "-"
    row["weird_addl"] = "-"
    row["weird_notice"] = "-"

    # Include profiling-only values as optional trace fields when accepted by API.
    row["_total_packets"] = total_packets
    row["_total_bytes"] = total_bytes
    row["_average_packet_size"] = avg_packet_size
    row["_packet_rate"] = packet_rate
    row["_unique_dst_ports"] = len(dst_port_counter)
    row["_syn_packets"] = int(tcp_flag_counter["syn"])

    return row

# Main loop: capture packets in windows, extract features, and send to prediction API.
def main() -> None:
    # Resolve the project root so the default metadata path works from any launch location.
    project_root = Path(__file__).resolve().parents[1]

    # Parse command-line arguments for the capture and prediction settings.
    parser = argparse.ArgumentParser(description="Windowed packet profiler -> IDS /predict sender")
    parser.add_argument("--api", default="http://127.0.0.1:8000/predict", help="Predict endpoint URL")
    parser.add_argument(
        "--metadata",
        default=str(project_root / "models" / "ton_iot" / "ton_iot_metadata.json"),
        help="Model metadata path",
    )
    parser.add_argument("--interface", default=None, help="Interface name (optional)")
    parser.add_argument("--window-seconds", type=float, default=3.0, help="Capture window duration")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    args = parser.parse_args()

    # Ensure the model metadata exists before starting packet capture.
    metadata_path = Path(args.metadata)
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    # Load the exact feature schema expected by the prediction API/model.
    feature_columns = load_feature_columns(metadata_path)
    print(f"Loaded feature schema with {len(feature_columns)} columns")
    print(f"Sending predictions to: {args.api}")

    # Continuously capture packets in fixed-size windows and send features to the API.
    while True:
        # Start packet capture on the selected interface, if provided.
        sniffer = AsyncSniffer(iface=args.interface, store=True)
        sniffer.start()

        # Capture packets for one analysis window.
        time.sleep(args.window_seconds)

        # Stop capture and collect the packets from this window.
        packets = sniffer.stop() or []

        # Convert captured packets into a feature row compatible with the model.
        features = build_window_features(packets, args.window_seconds, feature_columns)
        payload = {"features": features, "source": "packet-profiler"}

        # Send the features to the prediction endpoint and print the result.
        try:
            response = requests.post(args.api, json=payload, timeout=args.timeout)
            response.raise_for_status()
            data = response.json()
            label = data.get("predicted_label", "unknown")
            confidence = data.get("confidence")
            print(
                f"packets={len(packets):4d} bytes={int(features.get('_total_bytes', 0)):7d} "
                f"rate={features.get('_packet_rate', 0):8.2f}/s -> {label} ({confidence})"
            )
        except Exception as exc:
            # Report any capture, network, or API parsing errors without stopping the loop.
            print(f"prediction error: {exc}")


if __name__ == "__main__":
    main()
