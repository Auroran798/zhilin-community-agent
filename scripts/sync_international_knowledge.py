"""Download allowlisted official snapshots and merge their governed metadata."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_ROOT = ROOT / "data/knowledge"
ALLOWLIST = KNOWLEDGE_ROOT / "international_sources.csv"
METADATA = KNOWLEDGE_ROOT / "official_source_metadata.csv"
SOURCE_REGISTRY = KNOWLEDGE_ROOT / "source_registry.csv"
MANIFEST_ROOT = KNOWLEDGE_ROOT / "manifests"
MAX_BYTES = 10 * 1024 * 1024


def _validate_target(row: dict[str, str]) -> Path:
    parsed = urlparse(row["url"])
    if parsed.scheme != "https" or parsed.hostname != row["allowed_host"]:
        raise SystemExit(f"blocked_non_allowlisted_url:{row['url']}")
    destination = (KNOWLEDGE_ROOT / row["destination"]).resolve()
    if KNOWLEDGE_ROOT.resolve() not in destination.parents:
        raise SystemExit("destination_outside_knowledge_root")
    return destination


def _validate_payload(payload: bytes, content_type: str) -> None:
    if len(payload) > MAX_BYTES:
        raise RuntimeError("source_snapshot_too_large")
    if content_type == "application/pdf" and not payload.startswith(b"%PDF-"):
        raise RuntimeError("invalid_pdf_signature")
    if content_type == "text/html" and b"<html" not in payload[:4000].lower():
        raise RuntimeError("invalid_html_signature")


def _download_with_curl(row: dict[str, str], destination: Path) -> None:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl_not_available")
    temporary_handle = tempfile.NamedTemporaryFile(
        prefix="zhilin-official-", suffix=".part", delete=False
    )
    temporary_handle.close()
    temporary = Path(temporary_handle.name)
    try:
        command = [
            curl,
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--max-time",
            "180",
            "--connect-timeout",
            "20",
            "--retry",
            "3",
            "--retry-delay",
            "2",
            "--retry-max-time",
            "420",
            "--retry-all-errors",
            "--continue-at",
            "-",
            "--max-redirs",
            "5",
            "--proto",
            "=https",
            "--proto-redir",
            "=https",
            "--max-filesize",
            str(MAX_BYTES),
            "--user-agent",
            "zhilin-community-agent/1.4 controlled-source-snapshot",
            "--output",
            str(temporary),
            "--write-out",
            "\n%{url_effective}\n%{content_type}",
            row["url"],
        ]
        process = subprocess.run(command, capture_output=True, text=True, timeout=450)
        if process.returncode:
            raise RuntimeError(f"curl_download_failed:{process.stderr.strip()[:300]}")
        lines = [line.strip() for line in process.stdout.splitlines() if line.strip()]
        if len(lines) < 2:
            raise RuntimeError("curl_missing_response_metadata")
        final_url, content_type = lines[-2], lines[-1].split(";", 1)[0].lower()
        if urlparse(final_url).hostname != row["allowed_host"]:
            raise RuntimeError(f"redirected_outside_allowlist:{final_url}")
        if content_type != row["expected_content_type"]:
            raise RuntimeError(f"unexpected_content_type:{content_type}")
        payload = temporary.read_bytes()
        _validate_payload(payload, content_type)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination_temporary = destination.with_suffix(destination.suffix + ".part")
        shutil.copyfile(temporary, destination_temporary)
        os.replace(destination_temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _download_with_httpx(row: dict[str, str], destination: Path) -> None:
    with httpx.stream(
        "GET",
        row["url"],
        follow_redirects=True,
        timeout=45,
        headers={"User-Agent": "zhilin-community-agent/1.4 controlled-source-snapshot"},
    ) as response:
        response.raise_for_status()
        final = urlparse(str(response.url))
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if final.hostname != row["allowed_host"]:
            raise RuntimeError(f"redirected_outside_allowlist:{response.url}")
        if content_type != row["expected_content_type"]:
            raise RuntimeError(f"unexpected_content_type:{content_type}")
        payload = bytearray()
        for chunk in response.iter_bytes():
            payload.extend(chunk)
            if len(payload) > MAX_BYTES:
                raise RuntimeError("source_snapshot_too_large")
    _validate_payload(payload, content_type)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.write_bytes(payload)
    os.replace(temporary, destination)


def _download(row: dict[str, str], destination: Path) -> None:
    # curl is preferred because several government CDNs reset Python TLS
    # connections while still serving the same HTTPS resource to curl.
    if shutil.which("curl.exe") or shutil.which("curl"):
        _download_with_curl(row, destination)
    else:
        _download_with_httpx(row, destination)


def _merge_registry(results: list[dict[str, object]]) -> None:
    with METADATA.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        metadata_rows = list(reader)
    if not fieldnames or "checksum" not in fieldnames:
        raise RuntimeError("invalid_official_source_metadata_schema")
    manifests = {str(row["source_no"]): row for row in results}
    metadata_by_id = {row["source_no"]: row for row in metadata_rows}
    if set(manifests) != set(metadata_by_id):
        raise RuntimeError("allowlist_metadata_source_set_mismatch")
    with SOURCE_REGISTRY.open(encoding="utf-8", newline="") as handle:
        registry_rows = list(csv.DictReader(handle))
    retained = [row for row in registry_rows if row["source_no"] not in metadata_by_id]
    for row in metadata_rows:
        manifest = manifests[row["source_no"]]
        if row["source_url"] != manifest["source_url"]:
            raise RuntimeError(f"metadata_url_mismatch:{row['source_no']}")
        if row["local_path"] != manifest["local_path"]:
            raise RuntimeError(f"metadata_path_mismatch:{row['source_no']}")
        row["checksum"] = str(manifest["sha256"])
        row["actually_downloaded"] = "true"
    temporary = SOURCE_REGISTRY.with_suffix(".csv.part")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(retained + metadata_rows)
    os.replace(temporary, SOURCE_REGISTRY)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    MANIFEST_ROOT.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    with ALLOWLIST.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            destination = _validate_target(row)
            if args.refresh or not destination.exists():
                _download(row, destination)
            payload = destination.read_bytes()
            _validate_payload(payload, row["expected_content_type"])
            checksum = hashlib.sha256(payload).hexdigest()
            manifest = {
                "source_no": row["source_no"],
                "source_url": row["url"],
                "local_path": str(destination.relative_to(KNOWLEDGE_ROOT)).replace("\\", "/"),
                "acquired_at": datetime.now(UTC).isoformat(),
                "byte_size": len(payload),
                "sha256": checksum,
                "content_type": row["expected_content_type"],
                "download_policy": "https_exact_host_allowlist_v2",
            }
            (MANIFEST_ROOT / f"{row['source_no'].lower()}.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            results.append(manifest)
    _merge_registry(results)
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
