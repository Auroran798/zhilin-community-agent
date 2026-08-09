from __future__ import annotations

import shutil
import subprocess
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "artifacts/release/stage5-demo"


def copy(source: Path, destination: Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, destination)
    elif source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)


def copy_security_evidence() -> None:
    summary_path=ROOT/"artifacts/security/stage5_security_summary.json"
    copy(summary_path,PACKAGE/"reports/security/stage5_security_summary.json")
    summary=json.loads(summary_path.read_text(encoding="utf-8"))
    for check in summary.get("checks",[]):
        report=check.get("report")
        if not report: continue
        source=ROOT/report
        if source.is_file():
            relative=source.relative_to(ROOT/"artifacts/security")
            copy(source,PACKAGE/"reports/security"/relative)


def copy_e2e_evidence() -> None:
    report_path=ROOT/"artifacts/e2e/stage5_e2e_report.json"
    copy(report_path,PACKAGE/"reports/tests/e2e/stage5_e2e_report.json")
    report=json.loads(report_path.read_text(encoding="utf-8"))
    for name in report.get("artifacts",[]):
        source=ROOT/"artifacts/e2e"/Path(name).name
        if source.is_file(): copy(source,PACKAGE/"reports/tests/e2e"/source.name)


def main() -> None:
    # A release package is a derived artifact. Rebuild its exact, validated
    # contents so stale reports from an earlier run cannot survive.
    if PACKAGE.exists(): shutil.rmtree(PACKAGE)
    PACKAGE.mkdir(parents=True, exist_ok=True)
    for name in ("README.md", "RELEASE_NOTES.md", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md", ".env.example", "docker-compose.yml", "Dockerfile"):
        copy(ROOT / name, PACKAGE / ("env/.env.example" if name == ".env.example" else name))
    for name in ("DEMO_ACCOUNTS.md", "VIDEO_STATUS.md", "stage5_demo_script.md", "stage5_demo_storyboard.md", "stage5_demo_voiceover.md", "stage5_baseline_issues.md", "stage5_requirement_conflicts.md", "54_stage5_security_report.md", "53_stage5_performance_report.md", "51_stage5_evaluation_report.md", "52_stage5_e2e_test_report.md", "58_stage5_completion_report.md", "59_future_roadmap.md"):
        copy(ROOT / "docs" / name, PACKAGE / "docs" / name)
    copy(ROOT / "artifacts/evaluations/stage5_evaluation.json", PACKAGE / "reports/evaluations/stage5_evaluation.json")
    copy(ROOT / "artifacts/performance/stage5_performance.json", PACKAGE / "reports/performance/stage5_performance.json")
    copy_security_evidence()
    copy_e2e_evidence()
    for name in ("stage5_pytest.json","stage5_pytest.txt","junit.xml","coverage.xml"):
        copy(ROOT/"artifacts/tests"/name,PACKAGE/"reports/tests/pytest"/name)
    copy(ROOT / "artifacts/demo", PACKAGE / "demo")
    for name in ("run_e2e.py", "capture_demo_screenshots.py", "record_demo.py"):
        copy(ROOT / "scripts" / name, PACKAGE / "demo/scripts" / name)
    (PACKAGE / "known_issues.md").write_text("# Known issues\n\nSee docs/58_stage5_completion_report.md for actual validation status and limitations.\n", encoding="utf-8")
    subprocess.run([sys.executable, "scripts/generate_release_manifest.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "scripts/generate_checksums.py"], cwd=ROOT, check=True)
    print(PACKAGE)


if __name__ == "__main__":
    main()
