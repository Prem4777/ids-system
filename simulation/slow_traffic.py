import argparse
import time
import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Low-and-slow traffic simulator")
    parser.add_argument("--target", required=True, help="Defender laptop IP")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--duration", type=int, default=240, help="seconds")
    parser.add_argument("--interval", type=float, default=0.12, help="seconds between requests")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--paths", default="/health,/metadata,/events?limit=25")
    args = parser.parse_args()

    paths = [p.strip() for p in args.paths.split(",") if p.strip()]
    if not paths:
        paths = ["/health"]

    end = time.time() + args.duration
    sent = ok = fail = 0
    idx = 0

    print(
        f"[SLOW] target=http://{args.target}:{args.port} duration={args.duration}s "
        f"interval={args.interval}s paths={paths}"
    )

    while time.time() < end:
        path = paths[idx % len(paths)]
        idx += 1
        url = f"http://{args.target}:{args.port}{path}"
        sent += 1
        try:
            res = requests.get(url, timeout=args.timeout)
            if res.status_code == 200:
                ok += 1
            else:
                fail += 1
        except Exception:
            fail += 1
        time.sleep(max(args.interval, 0.0))

    print(f"[SLOW] done sent={sent} ok={ok} fail={fail}")


if __name__ == "__main__":
    main()
