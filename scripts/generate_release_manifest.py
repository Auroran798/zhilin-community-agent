from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "artifacts/release/stage5-demo"


def read_json(path: Path) -> dict:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return {"status": "NOT_RUN"}


def main() -> None:
    try: commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except subprocess.CalledProcessError: commit = "uncommitted-worktree"
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    manifest = {
        "project": "智邻管家物业社区管理智能体",
        "version": version,
        "release_type": "single-host demo",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "python": sys.version,
        "platform": platform.platform(),
        "test_summary": read_json(ROOT / "artifacts/tests/stage5_pytest.json"),
        "evaluation_summary": read_json(ROOT / "artifacts/evaluations/stage5_evaluation.json"),
        "performance_summary": read_json(ROOT / "artifacts/performance/stage5_performance.json"),
        "security_summary": read_json(ROOT / "artifacts/security/stage5_security_summary.json"),
        "known_limitations": ["SQLite/Chroma single-host demo", "offline Fake LLM default", "no real payment, access-control or camera integration"],
    }
    PACKAGE.mkdir(parents=True, exist_ok=True)
    (PACKAGE / "release_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
