# 阶段 3 评测集

`evals/agent/dataset.jsonl` 由 `scripts/seed_agent_cases.py` 生成，包含报修、工单、RAG、账单、费用核查、公告、巡检及高风险/提示词注入样本。评测不访问网络，使用 `FakeLLMProvider` 和确定性风险规则。运行 `python scripts/run_agent_eval.py` 会生成 `evals/agent/reports/latest.json`。
