"""Prepare a clean, offline submission runtime before starting the API.

The immutable image contains source snapshots and the governed source registry.
Mutable SQLite/Chroma data lives in /app/runtime so the submitted compose package
can be started repeatedly without re-importing the knowledge base every time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.getenv("SUBMISSION_RUNTIME_DIR", "/app/runtime"))
MARKER = RUNTIME / ".beijing-bootstrap-v1.json"


def run(*command: str) -> None:
    print(f"[bootstrap] running: {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def bootstrap() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    run(sys.executable, "-m", "alembic", "upgrade", "head")
    if MARKER.exists():
        print(f"[bootstrap] existing runtime verified by {MARKER.name}", flush=True)
        return

    run(sys.executable, "-m", "data.seed")
    run(
        sys.executable,
        "scripts/verify_source_registry.py",
        "--output",
        str(RUNTIME / "evidence/knowledge_source_governance.json"),
    )
    run(sys.executable, "scripts/import_knowledge.py", "--reindex-all")

    registry = ROOT / "data/knowledge/source_registry.csv"
    synthetic = ROOT / "data/demo_synthetic/beijing_property_ops_6000.jsonl"
    marker = {
        "schema": "beijing-submission-bootstrap-v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "product_mode": "domestic_beijing",
        "data_mode": "demo",
        "formal_semantic_quality": False,
        "offline_fallback": True,
        "source_registry_sha256": sha256(registry),
        "synthetic_dataset_sha256": sha256(synthetic),
    }
    temporary = MARKER.with_suffix(".tmp")
    temporary.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(MARKER)
    print(f"[bootstrap] clean runtime initialized: {MARKER}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    bootstrap()
    print(f"[bootstrap] starting: {' '.join(command)}", flush=True)
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
