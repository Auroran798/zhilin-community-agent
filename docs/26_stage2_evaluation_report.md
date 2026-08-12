# RAG 离线评测报告

质量模式：`offline_fallback`；正式质量声明：`不允许`。

Formal claims require a real multilingual embedding, external reranker, and at least 500 independently reviewed cases.

| 指标 | 结果 |
|---|---:|
| case_count | 128 |
| recall_at_5 | 1.0 |
| mrr_at_5 | 0.9153 |
| citation_source_accuracy | 1.0 |
| citation_completeness | 1.0 |
| refusal_precision | 1.0 |
| refusal_recall | 1.0 |
| refusal_f1 | 1.0 |
| jurisdiction_leakage_count | 0 |
| latency_avg_ms | 469.44 |
| latency_p95_ms | 774 |

本报告由受控语料和固定测试集自动生成。离线 hashing/reranker fallback 结果只用于回归，不作为多语种语义质量证明。
