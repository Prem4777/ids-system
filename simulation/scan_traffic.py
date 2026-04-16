import argparse
import socket
import time


def try_connect(host: str, port: int, timeout: float) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True
    except Exception:
        return False
    finally:
        try:
            sock.close()
        except Exception:
            pass


def parse_ports(raw: str) -> list[int]:
    ports: list[int] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            a, b = token.split("-", 1)
            start = int(a)
            end = int(b)
            for p in range(min(start, end), max(start, end) + 1):
                ports.append(p)
        else:
            ports.append(int(token))
    # Keep port list unique and stable.
    seen = set()
    uniq: list[int] = []
    for p in ports:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def main() -> None:
    parser = argparse.ArgumentParser(description="Controlled scanning-like traffic simulator")
    parser.add_argument("--target", required=True, help="Defender laptop IP")
    parser.add_argument("--ports", default="20-60,80,443,5000,8000", help="Comma list and ranges")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--delay-ms", type=float, default=8.0)
    parser.add_argument("--timeout", type=float, default=0.25)
    parser.add_argument("--cooldown-seconds", type=int, default=8)
    args = parser.parse_args()

    ports = parse_ports(args.ports)
    delay = max(args.delay_ms, 0.0) / 1000.0

    print(f"[SCAN] target={args.target} ports={len(ports)} rounds={args.rounds}")
    for r in range(1, args.rounds + 1):
        sent = ok = fail = 0
        t0 = time.time()
        print(f"[SCAN] round={r} start")
        for p in ports:
            sent += 1
            if try_connect(args.target, p, args.timeout):
                ok += 1
            else:
                fail += 1
            if delay > 0:
                time.sleep(delay)

        elapsed = time.time() - t0
        print(f"[SCAN] round={r} sent={sent} ok={ok} fail={fail} elapsed={elapsed:.2f}s")
        if r < args.rounds:
            print(f"[SCAN] cooldown={args.cooldown_seconds}s")
            time.sleep(args.cooldown_seconds)

    print("[SCAN] complete")


if __name__ == "__main__":
    main()
