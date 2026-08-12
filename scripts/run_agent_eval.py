"""Offline Agent regression evaluation; unexecuted capabilities stay NOT_MEASURED."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.llm import FakeLLMProvider
from agent.schemas import IntentResult
from agent.risk import inspect

DATASET=Path("evals/agent/dataset.jsonl")


def ratio(a,b): return round(a/b,4) if b else None


def main():
    data=[json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line]
    llm=FakeLLMProvider();intent_ok=tool_ok=risk_ok=intents=tools=risks=0;failures=[]
    for case in data:
        actual=llm.invoke_structured([{"role":"user","content":case["input"]}],IntentResult).intent
        if case.get("intent"):
            intents+=1;intent_ok+=actual==case["intent"]
            if actual!=case["intent"]: failures.append({"id":case["id"],"field":"intent","expected":case["intent"],"actual":actual})
            action={"repair_request":"create_work_order","bill_query":"get_bill_bundle","bill_review_request":"create_bill_review","announcement_draft":"create_announcement_draft","inspection_report":"create_rectification","knowledge_question":"query_rag"}.get(actual)
            if case.get("expected_tool"):
                tools+=1;tool_ok+=action==case["expected_tool"]
                if action!=case["expected_tool"]: failures.append({"id":case["id"],"field":"tool","expected":case["expected_tool"],"actual":action})
        if case.get("risk"):
            risks+=1;actual_risk=inspect(case["input"])[0];risk_ok+=actual_risk==case["risk"]
            if actual_risk!=case["risk"]: failures.append({"id":case["id"],"field":"risk","expected":case["risk"],"actual":actual_risk})
    controlled_path=Path("evals/beijing/latest_controlled_results.json")
    controlled=json.loads(controlled_path.read_text(encoding="utf-8")) if controlled_path.exists() else None
    measured={"intent_accuracy":ratio(intent_ok,intents),"tool_selection_accuracy":ratio(tool_ok,tools),"risk_detection_accuracy":ratio(risk_ok,risks),"beijing_policy_regression_pass_rate":controlled.get("metrics",{}).get("pass_rate") if controlled else None,"jurisdiction_leakage_count":controlled.get("metrics",{}).get("jurisdiction_leakage_count") if controlled else None}
    not_measured={name:"NOT_MEASURED: this offline classifier runner does not execute tools, writes, confirmations, or live RBAC" for name in ("slot_extraction_accuracy","tool_call_success_rate","confirmation_gate_accuracy","idempotency_success_rate","permission_isolation_rate","rag_answer_status_accuracy","citation_compliance_rate")}
    report={"evaluation_type":"offline_agent_regression","dataset_status":"regression_not_independently_reviewed_gold","case_count":len(data),"beijing_controlled_case_count":controlled.get("metrics",{}).get("case_count") if controlled else 0,"metrics":measured,"not_measured":not_measured,"breakdown":{"intent_cases":intents,"risk_cases":risks,"tool_cases":tools},"failures":failures}
    out=Path("evals/agent/reports/latest.json");out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(report,ensure_ascii=False))
    if failures or not controlled or measured["jurisdiction_leakage_count"]: raise SystemExit(1)


if __name__=="__main__": main()
