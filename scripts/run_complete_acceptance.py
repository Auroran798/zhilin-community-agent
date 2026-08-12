"""Single-command, non-destructive engineering acceptance for the complete demo."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def run(name,command,env=None):
    result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,encoding="utf-8",errors="replace",check=False)
    return {"name":name,"status":"PASS" if result.returncode==0 else "FAIL","returncode":result.returncode,"command":command,"stdout":result.stdout[-4000:],"stderr":result.stderr[-4000:]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--security",action="store_true");parser.add_argument("--require-formal-rag",action="store_true");args=parser.parse_args()
    test_env=os.environ.copy();test_env["APP_ENV"]="test"
    checks=[
        run("source_governance",[sys.executable,"scripts/verify_source_registry.py"]),
        run("migration_consistency",[sys.executable,"-m","alembic","check"]),
        run("full_regression",[sys.executable,"-m","pytest","-q","--disable-warnings"],test_env),
        run("agent_evaluation",[sys.executable,"scripts/run_agent_eval.py"]),
        run("beijing_controlled_regression",[sys.executable,"evals/beijing/run_controlled.py"]),
        run("beijing_security_gate",[sys.executable,"evals/beijing/run_security_gate.py"]),
        run("rag_evaluation",[sys.executable,"evals/rag/run.py"]),
    ]
    if args.security: checks.append(run("security_scan",[sys.executable,"scripts/run_security_scan.py"]))
    rag_path=ROOT/"evals/rag/latest_results.json";rag=json.loads(rag_path.read_text(encoding="utf-8")) if rag_path.exists() else {}
    security_path=ROOT/"evals/beijing/latest_security_results.json";security=json.loads(security_path.read_text(encoding="utf-8")) if security_path.exists() else {}
    synthetic_path=ROOT/"data/demo_synthetic/manifest.json";synthetic=json.loads(synthetic_path.read_text(encoding="utf-8")) if synthetic_path.exists() else {}
    metrics=rag.get("metrics",{});thresholds={"recall_at_5":0.92,"mrr_at_5":0.85,"citation_source_accuracy":0.98,"citation_completeness":0.98,"refusal_f1":0.95}
    offline_gate=all(metrics.get(name,0)>=value for name,value in thresholds.items()) and metrics.get("jurisdiction_leakage_count",1)==0 and security.get("permission_leakage_count",1)==0
    synthetic_validation=synthetic.get("validation",{});synthetic_gate=3000<=synthetic_validation.get("record_count",0)<=10000 and synthetic_validation.get("coverage_days",0)>=365 and synthetic.get("synthetic") is True
    formal=bool(rag.get("formal_evaluation"));blocking=[item["name"] for item in checks if item["status"]!="PASS"]
    if not offline_gate: blocking.append("offline_quality_gate")
    if not synthetic_gate: blocking.append("synthetic_data_gate")
    if args.require_formal_rag and not formal: blocking.append("formal_rag_prerequisites")
    report={"generated_at":datetime.now(UTC).isoformat(),"status":"PASS" if not blocking else "FAIL","blocking":blocking,"checks":checks,"offline_quality_gate":{"status":"PASS" if offline_gate else "FAIL","thresholds":thresholds,"metrics":metrics,"permission_leakage_count":security.get("permission_leakage_count")},"synthetic_data_gate":{"status":"PASS" if synthetic_gate else "FAIL","validation":synthetic_validation},"rag_quality_profile":rag.get("quality_profile"),"formal_rag_evaluation":formal,"release_scope":"Beijing-first domestic property assistant demo/research system; not a production property platform"}
    output=ROOT/"artifacts/acceptance/final_acceptance.json";output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":report["status"],"blocking":blocking,"checks":{item["name"]:item["status"] for item in checks},"formal_rag_evaluation":formal,"report":str(output.relative_to(ROOT)).replace("\\","/")},ensure_ascii=False))
    if blocking: raise SystemExit(1)


if __name__=="__main__": main()
