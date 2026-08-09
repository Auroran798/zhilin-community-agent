"""Run reproducible retrieval/citation/refusal metrics against local RAG data."""
import json, statistics, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from api.database import SessionLocal
from api.models import RagQueryLog, User
from rag.service import search

ROOT=Path(__file__).parent
def main():
    cases=[json.loads(line) for line in (ROOT/"dataset.jsonl").read_text(encoding="utf-8").splitlines() if line]
    db=SessionLocal(); user=db.query(User).filter_by(role="manager").first()
    if not user: raise SystemExit("Run data.seed and import_knowledge before evaluation")
    results=[]
    for case in cases:
        response=search(db,case["query"],user,case["scope"],top_k=5)
        titles={cite["title"] for cite in response["citations"]}
        citations_ok=all(c.get("title") and c.get("source_url") and c.get("version") for c in response["citations"])
        results.append({**case,"actual_status":response["answer_status"],"matched":case["expected_title"] in titles if case["expected_title"] else None,"citation_complete":citations_ok,"latency_ms":db.query(RagQueryLog).filter_by(id=response["query_log_id"]).first().latency_ms})
    answered=[r for r in results if r["expected_status"]=="answered"]; refused=[r for r in results if r["expected_status"]=="refused"]
    metrics={"case_count":len(results),"recall_at_5":round(sum(bool(r["matched"]) for r in answered)/len(answered),4),"citation_completeness":round(sum(r["citation_complete"] for r in answered)/len(answered),4),"safe_refusal_accuracy":round(sum(r["actual_status"] in {"refused","blocked"} for r in refused)/len(refused),4),"latency_avg_ms":round(statistics.mean(r["latency_ms"] for r in results),2),"latency_p95_ms":sorted(r["latency_ms"] for r in results)[max(0,int(len(results)*.95)-1)]}
    (ROOT/"latest_results.json").write_text(json.dumps({"metrics":metrics,"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
    report="# 阶段 2 RAG 评测报告\n\n| 指标 | 结果 |\n|---|---:|\n"+"\n".join(f"| {k} | {v} |" for k,v in metrics.items())+"\n\n说明：本报告由本地已导入语料和当前检索配置自动生成；结果用于回归比较，低分样本须人工检查来源、切块和阈值。\n"
    (Path("docs")/"26_stage2_evaluation_report.md").write_text(report,encoding="utf-8")
    print(json.dumps(metrics,ensure_ascii=False));db.close()
if __name__=="__main__": main()
