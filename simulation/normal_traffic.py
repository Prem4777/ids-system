import argparse
import time
import requests

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True, help="Main laptop IP, e.g. 192.168.43.120")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--duration", type=int, default=180, help="seconds")
    p.add_argument("--interval", type=float, default=1.0, help="seconds")
    args = p.parse_args()

    url = f"http://{args.target}:{args.port}/health"
    end = time.time() + args.duration
    sent = ok = fail = 0

    print(f"[NORMAL] {url} duration={args.duration}s interval={args.interval}s")
    while time.time() < end:
        sent += 1
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                ok += 1
            else:
                fail += 1
        except Exception:
            fail += 1
        time.sleep(args.interval)

    print(f"[NORMAL] done sent={sent} ok={ok} fail={fail}")

if __name__ == "__main__":
    main()