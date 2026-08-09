"""Record the executable browser demo; Playwright writes a WebM when supported."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    subprocess.run([sys.executable, "scripts/run_e2e.py"], cwd=ROOT, check=True)
    source = ROOT / "artifacts/e2e/video"
    target = ROOT / "artifacts/demo/video"
    target.mkdir(parents=True, exist_ok=True)
    videos = list(source.glob("*.webm"))
    for video in videos:
        shutil.copy2(video, target / "stage5_demo.webm")
    print("recorded" if videos else "no video emitted by the current browser runtime")


if __name__ == "__main__":
    main()
