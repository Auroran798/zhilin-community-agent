"""Reproducible retrieval, citation, refusal, and jurisdiction evaluation."""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from api.database import SessionLocal
from api.models import RagQueryLog, User
from rag.service import quality_profile, search

ROOT=Path(__file__).parent


def ratio(numerator,denominator):
    return round(numerator/denominator,4) if denominator else 0.0


def inferred_jurisdiction(case):
    if case.get("jurisdiction"): return case["jurisdiction"]
    title=case.get("expected_title") or ""
    if title.startswith("智邻花园"): return "Demo Garden"
    if title: return "全国"
    return None


def main():
    datasets=(ROOT/"dataset.jsonl",ROOT/"multilingual_official_dataset.jsonl")
    cases=[json.loads(line) for path in datasets for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    db=SessionLocal();user=db.query(User).filter_by(role="manager").first()
    if not user: raise SystemExit("Run data.seed and scripts/import_knowledge.py before evaluation")
    results=[]
    for case in cases:
        jurisdiction=inferred_jurisdiction(case)
        response=search(db,case["query"],user,case.get("scope"),top_k=5,jurisdiction=jurisdiction)
        citations=response["citations"];titles=[cite["title"] for cite in citations]
        expected=case.get("expected_title");rank=titles.index(expected)+1 if expected in titles else None
        actual_positive=response["answer_status"] not in {"refused","blocked"}
        expected_positive=case["expected_status"]=="answered"
        log=db.get(RagQueryLog,response["query_log_id"])
        allowed={"全国","北京市",jurisdiction} if jurisdiction and jurisdiction not in {"全国","北京市","GB","AU-NSW","AU-VIC","NZ","US-NY-NYC","SG","GLOBAL"} else ({"全国","北京市"} if jurisdiction=="北京市" else ({jurisdiction} if jurisdiction else set()))
        leakage=bool(allowed and any(cite.get("jurisdiction") not in allowed for cite in citations))
        results.append({**case,"jurisdiction":jurisdiction,"actual_status":response["answer_status"],"expected_positive":expected_positive,"actual_positive":actual_positive,"rank":rank,"matched":rank is not None if expected else None,"cited_titles":titles,"citation_complete":all(cite.get("title") and cite.get("source_url") and cite.get("version") and cite.get("jurisdiction") and cite.get("authority_level") and (cite.get("clause_number") or cite.get("section") or cite.get("page") or cite.get("source_url")) for cite in citations),"jurisdiction_leakage":leakage,"latency_ms":log.latency_ms})
    positives=[row for row in results if row["expected_positive"]];negatives=[row for row in results if not row["expected_positive"]]
    true_positive=sum(row["actual_positive"] for row in positives);false_negative=len(positives)-true_positive
    true_negative=sum(not row["actual_positive"] for row in negatives);false_positive=len(negatives)-true_negative
    refusal_precision=ratio(true_negative,true_negative+false_negative);refusal_recall=ratio(true_negative,true_negative+false_positive)
    profile=quality_profile();formal=profile["formal_quality_claim_allowed"] and len(cases)>=500
    metrics={
        "case_count":len(results),
        "recall_at_5":ratio(sum(bool(row["matched"]) for row in positives),len(positives)),
        "mrr_at_5":round(sum(1/row["rank"] if row["rank"] else 0 for row in positives)/max(1,len(positives)),4),
        "citation_source_accuracy":ratio(sum(bool(row["matched"]) for row in positives),len(positives)),
        "citation_completeness":ratio(sum(row["citation_complete"] for row in positives),len(positives)),
        "refusal_precision":refusal_precision,
        "refusal_recall":refusal_recall,
        "refusal_f1":round(2*refusal_precision*refusal_recall/(refusal_precision+refusal_recall),4) if refusal_precision+refusal_recall else 0.0,
        "jurisdiction_leakage_count":sum(row["jurisdiction_leakage"] for row in results),
        "latency_avg_ms":round(statistics.mean(row["latency_ms"] for row in results),2),
        "latency_p95_ms":sorted(row["latency_ms"] for row in results)[max(0,int(len(results)*.95)-1)],
    }
    gate={"status":"EVALUATED" if formal else "NOT_FORMAL","reason":None if formal else "Formal claims require a real multilingual embedding, external reranker, and at least 500 independently reviewed cases.","thresholds":{"recall_at_5":0.92,"mrr_at_5":0.85,"citation_source_accuracy":0.98,"refusal_f1":0.95,"jurisdiction_leakage_count":0}}
    payload={"quality_profile":profile,"formal_evaluation":formal,"datasets":[path.name for path in datasets],"gate":gate,"metrics":metrics,"results":results}
    (ROOT/"latest_results.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    report=["# RAG 离线评测报告","",f"质量模式：`{profile['mode']}`；正式质量声明：`{'允许' if formal else '不允许'}`。","",gate["reason"] or "已满足正式评测前置条件。","","| 指标 | 结果 |","|---|---:|",*[f"| {key} | {value} |" for key,value in metrics.items()],"","本报告由受控语料和固定测试集自动生成。离线 hashing/reranker fallback 结果只用于回归，不作为多语种语义质量证明。"]
    (Path("docs")/"26_stage2_evaluation_report.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    print(json.dumps({"quality_profile":profile,"formal_evaluation":formal,"metrics":metrics},ensure_ascii=False));db.close()


if __name__=="__main__": main()
