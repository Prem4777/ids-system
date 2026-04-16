import argparse
import concurrent.futures
import csv
import random
import time
from datetime import datetime
from pathlib import Path
import requests

def hit(url, timeout):
    try:
        status_code = requests.get(url, timeout=timeout).status_code
        return status_code == 200, status_code
    except Exception:
        return False, None


def parse_paths(raw: str) -> list[str]:
    paths = []
    for part in raw.split(","):
        p = part.strip()
        if not p:
            continue
        if not p.startswith("/"):
            p = "/" + p
        paths.append(p)
    return paths or ["/health"]


def make_log_path(raw_path: str | None) -> Path:
    if raw_path:
        path = Path(raw_path)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(__file__).resolve().parent / "logs" / f"burst_run_{stamp}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_summary(log_path: Path, rows: list[dict[str, object]]) -> None:
    headers = [
        "timestamp",
        "round",
        "duration_seconds",
        "endpoint_paths",
        "request_rate",
        "workers",
        "sent",
        "ok",
        "fail",
    ]
    with log_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True, help="Main laptop IP")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--burst-seconds", type=int, default=20)
    p.add_argument("--cooldown-seconds", type=int, default=15)
    p.add_argument("--workers", type=int, default=40)
    p.add_argument("--timeout", type=float, default=1.5)
    p.add_argument("--endpoint-paths", default="/health,/metadata,/events?limit=20", help="Comma-separated endpoint paths")
    p.add_argument("--request-rate", type=float, default=120.0, help="Approximate requests per second")
    p.add_argument("--jitter-ms", type=float, default=4.0, help="Random jitter in milliseconds")
    p.add_argument("--log-file", default=None, help="CSV output file path (optional)")
    args = p.parse_args()

    endpoint_paths = parse_paths(args.endpoint_paths)
    base_url = f"http://{args.target}:{args.port}"
    health_url = f"{base_url}/health"
    print(f"[BURST] target={base_url}")
    print(f"[BURST] endpoints={endpoint_paths}")

    # Fail fast if defender is unreachable.
    try:
        requests.get(health_url, timeout=max(2.0, args.timeout))
    except Exception as exc:
        raise SystemExit(f"[BURST] precheck failed for {health_url}: {exc}")

    log_rows: list[dict[str, object]] = []
    log_path = make_log_path(args.log_file)

    base_gap = 1.0 / max(args.request_rate, 1.0)
    jitter_sec = max(args.jitter_ms, 0.0) / 1000.0

    for r in range(1, args.rounds + 1):
        sent = ok = fail = 0
        end = time.time() + args.burst_seconds
        print(f"[BURST] round={r} start")

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = []
            idx = 0
            while time.time() < end:
                path = endpoint_paths[idx % len(endpoint_paths)]
                idx += 1
                futures.append(ex.submit(hit, f"{base_url}{path}", args.timeout))
                sent += 1
                sleep_for = max(0.0, base_gap + random.uniform(-jitter_sec, jitter_sec))
                if sleep_for > 0:
                    time.sleep(sleep_for)
            for f in futures:
                req_ok, _status = f.result()
                if req_ok:
                    ok += 1
                else:
                    fail += 1

        print(f"[BURST] round={r} sent={sent} ok={ok} fail={fail}")
        log_rows.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "round": r,
                "duration_seconds": args.burst_seconds,
                "endpoint_paths": "|".join(endpoint_paths),
                "request_rate": args.request_rate,
                "workers": args.workers,
                "sent": sent,
                "ok": ok,
                "fail": fail,
            }
        )
        if r < args.rounds:
            print(f"[BURST] cooldown={args.cooldown_seconds}s")
            time.sleep(args.cooldown_seconds)

    write_summary(log_path, log_rows)
    print(f"[BURST] summary log: {log_path}")
    print("[BURST] complete")

if __name__ == "__main__":
    main()