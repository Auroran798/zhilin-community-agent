from __future__ import annotations

from pathlib import Path

ROOT = Path("data/public_real")
RAW_DIR = ROOT / "raw"
PROCESSED_DIR = ROOT / "processed"
NORMALIZED_DIR = ROOT / "normalized"
MANIFEST_DIR = ROOT / "manifests"
SAMPLES_DIR = ROOT / "samples"
PROFILE_DIR = Path("artifacts/data_quality")
USER_AGENT = "zhilin-community-agent-stage6/0.6 (public-data-demo; no-auth)"
DOWNLOAD_PAGE_SIZE = 5_000
DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOAD_RETRIES = 3

for directory in (RAW_DIR, PROCESSED_DIR, NORMALIZED_DIR, MANIFEST_DIR, SAMPLES_DIR, PROFILE_DIR):
    directory.mkdir(parents=True, exist_ok=True)
