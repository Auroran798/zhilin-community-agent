from __future__ import annotations

import json
import re
import subprocess
import sys
import os
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    # The shared Windows Python environment can expose an inaccessible user
    # temp directory. Keep pytest's disposable files inside this workspace.
    base_temp = ROOT / "tmp" / f"pytest-basetemp-{uuid.uuid4().hex}"
    env=os.environ.copy();env["APP_ENV"]="test"
    result = subprocess.run([sys.executable, "-m", "pytest", "--disable-warnings", "--basetemp", str(base_temp), "-p", "no:cacheprovider"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    combined = result.stdout + "\n" + result.stderr
    match = re.search(r"(\d+) passed(?:, (\d+) failed)?(?:, (\d+) skipped)?", combined)
    report = {"returncode": result.returncode, "passed": int(match.group(1)) if match else 0, "failed": int(match.group(2) or 0) if match else 0, "skipped": int(match.group(3) or 0) if match else 0, "status": "PASS" if result.returncode == 0 else "FAIL", "output": "artifacts/tests/stage5_pytest.txt"}
    output = ROOT / "artifacts/tests"; output.mkdir(parents=True, exist_ok=True)
    (output / "stage5_pytest.txt").write_text(combined, encoding="utf-8")
    (output / "stage5_pytest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if result.returncode: raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
