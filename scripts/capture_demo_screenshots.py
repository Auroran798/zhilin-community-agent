"""Copy actual Stage 5 browser screenshots into the demo-artifact location."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "artifacts/e2e"
target = ROOT / "artifacts/demo/screenshots"


def main() -> None:
    subprocess.run([sys.executable, "scripts/run_e2e.py"], cwd=ROOT, check=True)
    target.mkdir(parents=True, exist_ok=True)
    for file in source.glob("*.png"):
        shutil.copy2(file, target / file.name)
    print(f"captured {len(list(target.glob('*.png')))} screenshot(s) in {target}")


if __name__ == "__main__":
    main()
