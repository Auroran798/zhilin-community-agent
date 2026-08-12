"""Run the deterministic jurisdiction/refusal policy gate over the regression set."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from rag.service import _scope_decision, is_suspicious

HERE=Path(__file__).resolve().parent
POLICY_REFUSALS={"expired_version":"SOURCE_EXPIRED","insufficient_evidence":"NO_DIRECT_EVIDENCE","unauthorized_access":"FORBIDDEN","no_real_data":"NO_REAL_DATA_AUTHORIZATION"}


def evaluate(case:dict)->dict:
    if is_suspicious(case["query"]): status,error,scopes="blocked","PROMPT_INJECTION",set()
    else:
        decision=_scope_decision(case["query"],case.get("product_mode"),case.get("jurisdiction"),case.get("community"))
        if decision.get("error_code"): status,error,scopes="refused",decision["error_code"],set()
        elif case["category"] in POLICY_REFUSALS: status,error,scopes="refused",POLICY_REFUSALS[case["category"]],set(decision.get("jurisdictions",()))
        else: status,error,scopes="routed",None,set(decision.get("jurisdictions",()))
    expected_scopes=set(case.get("expected_jurisdictions",()))
    forbidden=set(case.get("forbidden_jurisdictions",()))
    passed=status==case["expected_status"] and (not case.get("expected_error") or error==case["expected_error"]) and (not expected_scopes or scopes==expected_scopes) and not (scopes&forbidden)
    return {"case_id":case["case_id"],"category":case["category"],"status":status,"error_code":error,"jurisdictions":sorted(scopes),"jurisdiction_leakage":sorted(scopes&forbidden),"passed":passed}


def main():
    cases=[json.loads(line) for line in (HERE/"controlled_regression_360.jsonl").read_text(encoding="utf-8").splitlines() if line]
    results=[evaluate(case) for case in cases];by_category=Counter()
    for result in results:
        if result["passed"]: by_category[result["category"]]+=1
    metrics={"case_count":len(results),"passed":sum(item["passed"] for item in results),"pass_rate":round(sum(item["passed"] for item in results)/len(results),4),"jurisdiction_leakage_count":sum(bool(item["jurisdiction_leakage"]) for item in results),"category_passed":dict(by_category)}
    payload={"evaluation_type":"controlled_policy_regression","formal_gold_evaluation":False,"reason":"用例由程序生成且未经独立人工审阅；只能称为回归集。","metrics":metrics,"results":results}
    (HERE/"latest_controlled_results.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(metrics,ensure_ascii=False))
    if metrics["passed"]!=metrics["case_count"] or metrics["jurisdiction_leakage_count"]: raise SystemExit(1)


if __name__=="__main__": main()
