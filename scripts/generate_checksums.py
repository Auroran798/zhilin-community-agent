from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "artifacts/release/stage5-demo"


def main() -> None:
    lines = []
    for path in sorted(p for p in PACKAGE.rglob("*") if p.is_file() and p.name != "checksums.sha256"):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(PACKAGE).as_posix()}")
    (PACKAGE / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"checksummed {len(lines)} file(s)")


if __name__ == "__main__":
    main()
