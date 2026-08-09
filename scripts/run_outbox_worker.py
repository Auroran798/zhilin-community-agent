from __future__ import annotations

import argparse
import time

from api.database import SessionLocal
from api.outbox import process_pending


def run_once(limit: int) -> dict[str, int]:
    with SessionLocal() as db:
        return process_pending(db, limit)


def main() -> None:
    parser = argparse.ArgumentParser(description="Process durable 智邻管家 outbox events")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    while True:
        result = run_once(args.limit)
        print(result, flush=True)
        if args.once:
            return
        time.sleep(max(0.5, args.interval))


if __name__ == "__main__":
    main()
