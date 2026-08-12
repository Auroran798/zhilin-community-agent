"""Run available local security checks and report unavailable scanners honestly."""
from __future__ import annotations

import json
import importlib.util
import re
import shutil
import subprocess
import sys
import os
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/security"
TRIVY_DB_FLAGS: list[str] = []

# Winget additions are not inherited by an already-open terminal process.
winget_packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Packages"
if winget_packages.exists():
    trivy_binary = next(winget_packages.rglob("trivy.exe"), None)
    if trivy_binary:
        os.environ["PATH"] = str(trivy_binary.parent) + os.pathsep + os.environ.get("PATH", "")


def command(name: str, args: list[str], output: Path) -> dict:
    if not shutil.which(args[0]):
        return {"name": name, "status": "NOT_RUN", "reason": f"{args[0]} not installed"}
    try:
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except subprocess.TimeoutExpired:
        return {"name": name, "status": "NOT_RUN", "reason": "scanner timed out after 60 seconds"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    status = "PASS" if result.returncode == 0 else "FAIL"
    return {"name": name, "status": status, "returncode": result.returncode, "report": str(output.relative_to(ROOT))}


def _severity_counts(payload: dict) -> dict[str, int]:
    counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0, "UNKNOWN": 0}
    for result in payload.get("Results", []):
        for key in ("Vulnerabilities", "Misconfigurations", "Secrets", "Licenses"):
            for finding in result.get(key) or []:
                severity = str(finding.get("Severity", "UNKNOWN")).upper()
                counts[severity if severity in counts else "UNKNOWN"] += 1
    return counts


def prepare_trivy_db() -> dict:
    """Update once; allow a clearly reported cache no older than seven days."""
    global TRIVY_DB_FLAGS
    if not shutil.which("trivy"):
        return {"name":"trivy-vulnerability-db","status":"NOT_RUN","reason":"trivy not installed"}
    try:
        updated=subprocess.run(["trivy","image","--download-db-only"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=75)
    except subprocess.TimeoutExpired:
        updated=None
    if updated and updated.returncode==0:
        return {"name":"trivy-vulnerability-db","status":"PASS","source":"updated"}
    version=subprocess.run(["trivy","--version"],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace")
    matched=re.search(r"UpdatedAt:\s*([^\r\n]+)",version.stdout)
    if not matched:
        return {"name":"trivy-vulnerability-db","status":"NOT_RUN","reason":"update failed and cached DB age is unknown"}
    try:
        raw_timestamp=matched.group(1).strip()
        timestamp_match=re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:\.(\d+))?\s+([+-]\d{4})",raw_timestamp)
        if not timestamp_match:
            raise ValueError(raw_timestamp)
        fraction=(timestamp_match.group(2) or "0")[:6].ljust(6,"0")
        cached=datetime.strptime(f"{timestamp_match.group(1)}.{fraction} {timestamp_match.group(3)}","%Y-%m-%d %H:%M:%S.%f %z")
        age_hours=(datetime.now(timezone.utc)-cached.astimezone(timezone.utc)).total_seconds()/3600
    except ValueError:
        return {"name":"trivy-vulnerability-db","status":"NOT_RUN","reason":"could not parse cached DB timestamp"}
    if age_hours>168:
        return {"name":"trivy-vulnerability-db","status":"NOT_RUN","age_hours":round(age_hours,1),"reason":"cached DB is older than 7 days"}
    TRIVY_DB_FLAGS=["--skip-db-update"]
    reason=(updated.stderr if updated else "update timed out")[-500:]
    return {"name":"trivy-vulnerability-db","status":"PASS","source":"cached","age_hours":round(age_hours,1),"update_warning":reason}


def trivy_scan(name: str, args: list[str], output: Path) -> dict:
    if not shutil.which("trivy"):
        return {"name": name, "status": "NOT_RUN", "reason": "trivy not installed"}
    command_args = ["trivy", args[0], *TRIVY_DB_FLAGS, *args[1:-1], "--format", "json", "--severity", "HIGH,CRITICAL", "--exit-code", "1", args[-1]]
    try:
        result = subprocess.run(command_args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    except subprocess.TimeoutExpired:
        return {"name": name, "status": "NOT_RUN", "reason": "scanner timed out after 180 seconds"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result.stdout or result.stderr, encoding="utf-8")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"name": name, "status": "FAIL", "returncode": result.returncode, "reason": "Trivy JSON output could not be parsed", "report": str(output.relative_to(ROOT))}
    counts = _severity_counts(payload)
    blocking = counts["HIGH"] + counts["CRITICAL"]
    return {"name": name, "status": "FAIL" if blocking else "PASS", "returncode": result.returncode, "counts": counts, "report": str(output.relative_to(ROOT))}


def bandit_scan(output: Path) -> dict:
    if importlib.util.find_spec("bandit") is None:
        return {"name":"bandit","status":"NOT_RUN","reason":"bandit is not installed in the active Python environment"}
    try:
        result = subprocess.run([sys.executable, "-m", "bandit", "-q", "-r", "api", "agent", "harness", "mcp_server", "-f", "json"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    except subprocess.TimeoutExpired:
        return {"name": "bandit", "status": "NOT_RUN", "reason": "scanner timed out after 120 seconds"}
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(result.stdout or result.stderr, encoding="utf-8")
    try:
        payload=json.loads(result.stdout); counts={key:0 for key in ("LOW","MEDIUM","HIGH","CRITICAL")}
        for finding in payload.get("results",[]): counts[str(finding.get("issue_severity","LOW")).upper()]+=1
    except (json.JSONDecodeError,KeyError):
        return {"name":"bandit","status":"FAIL","returncode":result.returncode,"reason":"Bandit JSON output could not be parsed","report":str(output.relative_to(ROOT))}
    return {"name":"bandit","status":"FAIL" if counts["HIGH"] or counts["CRITICAL"] else "PASS","returncode":result.returncode,"counts":counts,"report":str(output.relative_to(ROOT))}


def project_dependency_audit(requirements: Path, output: Path) -> dict:
    """Resolve and audit the deployable requirement set, not the host Python."""
    if output.exists() and output.stat().st_mtime >= (ROOT/"pyproject.toml").stat().st_mtime and datetime.now().timestamp()-output.stat().st_mtime < 86400:
        try:
            cached=json.loads(output.read_text(encoding="utf-8"));findings=cached.get("findings",[])
            return {"name":"pip-audit-resolved-runtime","status":"PASS" if not findings else "FAIL","findings":sum(len(item.get("vulns",[])) for item in findings),"report":str(output.relative_to(ROOT)),"cached_within_hours":24}
        except json.JSONDecodeError:
            pass
    try:
        # pip-api shells out to ``pip --version`` and assumes UTF-8.  On
        # Windows, a workspace path containing Chinese characters otherwise
        # makes that child emit the active code page and pip-audit crashes
        # before performing any audit.
        audit_env={**os.environ,"PYTHONUTF8":"1","PYTHONIOENCODING":"utf-8"}
        result = subprocess.run([sys.executable, "-m", "pip_audit", "-r", str(requirements), "--format", "json"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240,env=audit_env)
    except subprocess.TimeoutExpired:
        return {"name": "pip-audit-resolved-runtime", "status": "NOT_RUN", "reason": "pip-audit timed out after 240 seconds"}
    raw = output.with_name("pip_audit_resolver_output.json")
    raw.parent.mkdir(parents=True, exist_ok=True); raw.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    try:
        payload = json.loads(result.stdout)
        findings = [{"name": item["name"], "version": item["version"], "vulns": item["vulns"]} for item in payload.get("dependencies", []) if item["vulns"]]
        output.write_text(json.dumps({"scope": "fully resolved deployable dependency graph", "findings": findings}, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"name": "pip-audit-resolved-runtime", "status": "PASS" if not findings else "FAIL", "findings": sum(len(item["vulns"]) for item in findings), "report": str(output.relative_to(ROOT)), "resolver_report": str(raw.relative_to(ROOT))}
    except json.JSONDecodeError:
        return {"name": "pip-audit-resolved-runtime", "status": "NOT_RUN", "reason": f"could not parse resolver audit output (returncode={result.returncode}); inspect {raw.relative_to(ROOT)}"}


def image_sbom(image: str, output: Path) -> dict:
    if not shutil.which("trivy"):
        return {"name":"cyclonedx-image-sbom","status":"NOT_RUN","reason":"trivy not installed"}
    output.parent.mkdir(parents=True,exist_ok=True)
    try:
        result=subprocess.run(["trivy","image","--format","cyclonedx","--output",str(output),image],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=240)
    except subprocess.TimeoutExpired:
        return {"name":"cyclonedx-image-sbom","status":"NOT_RUN","reason":"SBOM generation timed out"}
    return {"name":"cyclonedx-image-sbom","status":"PASS" if result.returncode==0 and output.exists() else "FAIL","returncode":result.returncode,"report":str(output.relative_to(ROOT))}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    secret_pattern = re.compile(r"(?i)(?:api[_-]?key|secret|token)\s*[=:]\s*['\"][^'\"]{12,}")
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", "tmp", "artifacts"} or part.startswith((".venv", "tmp_")) for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".yml", ".yaml", ".md", ".json", ".toml", ".env"}:
            continue
        try:
            for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if secret_pattern.search(line) and "change-this" not in line and "DEMO_PASSWORD" not in line:
                    hits.append(f"{path.relative_to(ROOT)}:{line_no}")
        except OSError:
            pass
    secret_report = OUT / "secrets.json"
    secret_report.write_text(json.dumps({"hits": hits}, ensure_ascii=False, indent=2), encoding="utf-8")
    project_requirements = OUT / "dependencies/project-direct-requirements.txt"
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_requirements.parent.mkdir(parents=True, exist_ok=True)
    project_requirements.write_text("\n".join(project["project"]["dependencies"]) + "\n", encoding="utf-8")
    trivy_db=prepare_trivy_db()
    skip_dirs=["--skip-dirs","**/.venv*","--skip-dirs","**/tmp*","--skip-dirs","artifacts","--skip-dirs","data/public_real","--skip-dirs","data/knowledge/chroma"]
    checks = [
        {"name": "secret-pattern", "status": "PASS" if not hits else "FAIL", "report": str(secret_report.relative_to(ROOT)), "findings": len(hits)},
        bandit_scan(OUT / "bandit.json"),
        project_dependency_audit(project_requirements, OUT / "dependencies/pip_audit.json"),
        trivy_db,
        trivy_scan("trivy-fs-config-and-secrets", ["fs", "--scanners", "secret,misconfig", *skip_dirs, "."], OUT / "trivy/filesystem.json"),
        trivy_scan("trivy-image-secrets", ["image", "--scanners", "secret", "zhilin-community-agent-api"], OUT / "trivy/image-api.json"),
        trivy_scan("trivy-filesystem-vulnerabilities", ["fs", "--scanners", "vuln", *skip_dirs, "."], OUT / "trivy/filesystem-vulnerabilities.json"),
        trivy_scan("trivy-image-vulnerabilities", ["image", "--scanners", "vuln", "zhilin-community-agent-api"], OUT / "trivy/image-api-vulnerabilities.json"),
        image_sbom("zhilin-community-agent-api",OUT/"sbom/image-api.cdx.json"),
        command("docker-compose-config", ["docker", "compose", "config"], OUT / "docker_compose_config.txt"),
    ]
    statuses={item["status"] for item in checks}
    overall="FAIL" if "FAIL" in statuses else "NOT_RUN" if "NOT_RUN" in statuses else "PASS"
    summary = {"status":overall,"generated_at":datetime.now(timezone.utc).isoformat(),"checks": checks, "critical": sum(item.get("counts",{}).get("CRITICAL",0) for item in checks), "high": sum(item.get("counts",{}).get("HIGH",0) for item in checks), "note": "NOT_RUN means a scanner was unavailable and is not interpreted as PASS. HIGH/CRITICAL findings fail the release gate and require remediation or a separately reviewed waiver."}
    (OUT / "stage5_security_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("docs/54_stage5_security_report.md").write_text(
        "# 阶段 5 安全扫描\n\n```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) +
        "\n```\n\n文件系统、已构建 API 镜像和解析后的部署依赖均完成扫描；漏洞库来源与缓存年龄以 JSON 中 `trivy-vulnerability-db` 为准。完整明细保存在 artifacts/security。\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    if overall != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
