"""Conservative release gate: NOT_RUN never counts as PASS."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ["README.md", ".env.example", "docker-compose.yml", "VERSION", "CHANGELOG.md", "RELEASE_NOTES.md", "docs/DEMO_ACCOUNTS.md", "docs/stage5_demo_script.md", "scripts/run_e2e.py", "scripts/run_security_scan.py", "scripts/build_release_package.py"]


def main() -> None:
    checks = []
    for item in REQUIRED:
        checks.append({"check": f"required:{item}", "status": "PASS" if (ROOT / item).exists() else "FAIL"})
    compose = subprocess.run(["docker", "compose", "config", "--quiet"], cwd=ROOT, capture_output=True, text=True)
    checks.append({"check": "docker-compose-config", "status": "PASS" if compose.returncode == 0 else "FAIL"})
    env = (ROOT / ".env.example").read_text(encoding="utf-8", errors="ignore") if (ROOT / ".env.example").exists() else ""
    checks.append({"check": "env-template-no-real-secret", "status": "PASS" if not re.search(r"sk-[A-Za-z0-9]{20,}", env) else "FAIL"})
    commit=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,capture_output=True,text=True)
    checks.append({"check":"git-commit-present","status":"PASS" if commit.returncode==0 else "FAIL"})
    dirty=subprocess.run(["git","status","--porcelain","--untracked-files=no"],cwd=ROOT,capture_output=True,text=True)
    checks.append({"check":"tracked-worktree-clean","status":"PASS" if dirty.returncode==0 and not dirty.stdout.strip() else "FAIL"})
    for artifact, label in [("artifacts/evaluations/stage5_evaluation.json", "evaluation"), ("artifacts/performance/stage5_performance.json", "performance"), ("artifacts/security/stage5_security_summary.json", "security"), ("artifacts/e2e/stage5_e2e_report.json", "browser-e2e"), ("artifacts/release/stage5-demo/release_manifest.json", "release-manifest"), ("artifacts/release/stage5-demo/checksums.sha256", "checksums")]:
        status = "NOT_RUN"
        path = ROOT / artifact
        if path.exists():
            status = "PASS"
            if path.suffix == ".json":
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if payload.get("status") == "FAIL": status = "FAIL"
                    if label == "security":
                        statuses = [item.get("status") for item in payload.get("checks", [])]
                        if payload.get("critical",0)>0 or payload.get("high",0)>0 or "FAIL" in statuses: status = "FAIL"
                        elif "NOT_RUN" in statuses: status = "NOT_RUN"
                    if label == "browser-e2e":
                        browser_flows=[item for item in payload.get("scenarios",[]) if item.get("evidence_type")=="browser_business_flow" and item.get("status")=="PASS"]
                        if payload.get("status")!="PASS" or len(browser_flows)<3: status="FAIL"
                    if label == "release-manifest" and (payload.get("git_commit") in {None,"","uncommitted-worktree"}): status="FAIL"
                except json.JSONDecodeError: status = "FAIL"
        checks.append({"check": label, "status": status, "artifact": artifact})
    checksum_file=ROOT/"artifacts/release/stage5-demo/checksums.sha256"
    checksum_status="NOT_RUN"
    if checksum_file.exists():
        checksum_status="PASS"
        for line in checksum_file.read_text(encoding="utf-8",errors="ignore").splitlines():
            if not line.strip():continue
            expected,relative=line.split(maxsplit=1);target=checksum_file.parent/relative.lstrip("* ")
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=expected:checksum_status="FAIL";break
    checks.append({"check":"checksum-content-validation","status":checksum_status})
    summary = {"PASS": sum(x["status"] == "PASS" for x in checks), "FAIL": sum(x["status"] == "FAIL" for x in checks), "NOT_RUN": sum(x["status"] == "NOT_RUN" for x in checks)}
    result = {"checks": checks, "summary": summary, "release_ready": summary["FAIL"] == 0 and summary["NOT_RUN"] == 0}
    output = ROOT / "artifacts/release/stage5_check.json"
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if not result["release_ready"]: raise SystemExit(1)


if __name__ == "__main__":
    main()
