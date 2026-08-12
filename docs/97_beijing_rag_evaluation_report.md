# 北京物业 RAG 评测报告

执行日期：2026-08-10  
命令：`python evals/rag/run.py`

## 结论

128 条固定 RAG 回归集达到本阶段数值门槛，且辖区泄漏为 0。但当前配置是 `offline_fallback`，没有真实多语种 embedding 和外部 reranker；数据集也不足 500 条且未经过独立人工审阅，因此 `formal_evaluation=false`，不得据此宣称正式多语种语义质量。

| 指标 | 门槛 | 实测 | 结果 |
| --- | ---: | ---: | --- |
| Recall@5 | ≥ 0.92 | 1.0000 | 通过 |
| MRR@5 | ≥ 0.85 | 0.9153 | 通过 |
| 引用来源正确率 | ≥ 0.98 | 1.0000 | 通过 |
| 引用完整率 | ≥ 0.98 | 1.0000 | 通过 |
| 拒答 F1 | ≥ 0.95 | 1.0000 | 通过 |
| jurisdiction 泄漏 | 0 | 0 | 通过 |

补充指标：拒答 precision 1.0000、拒答 recall 1.0000、平均延迟 469.44 ms、P95 延迟 774 ms。延迟是最终统一验收时的本机离线回归结果，不是生产 SLA。

机器可读明细见 [latest_results.json](../evals/rag/latest_results.json)，自动生成的基础报告见 [26_stage2_evaluation_report.md](26_stage2_evaluation_report.md)。

## 实际检索链路

1. 在检索前执行角色/社区权限、产品模式、`jurisdiction`、`answerable`、`review_status`、生效/失效时间和当前版本过滤。
2. `domestic_beijing` 按全国 → 北京市 → 当前小区组成适用链；全国问题只使用全国资料。
3. `international_research` 只允许单一精确外国辖区，外国来源不进入北京模式。
4. 对授权候选执行 BM25、Dense、RRF、每文档候选保护、文档级去重和 reranker。
5. 当前 Dense 为 hash fallback，reranker 为 lexical fallback；系统在 API 和报告中显式暴露此质量配置。
6. 证据不足、失效来源、跨辖区混问、外国资料被要求作为北京依据、提示词注入、赔偿/减费/改账/责任承诺均触发拒答或阻断。

## 本轮发现并修复的问题

统一验收第一次运行发现两个真实缺陷：历史合成公告的引用地域为空；“别的小区停车费”错误套用了当前 Demo 小区。修复后增加了社区地域回填和跨小区 `COMMUNITY_REQUIRED` 拒答，10 项产品模式聚焦测试和 128 条 RAG 重评均通过。

## 评测边界

- 128 条集合小于正式评测所需 500 条。
- 自动或工程人员维护的回归集不是独立人工金标。
- hash embedding 不能证明中文、英文或跨语种语义相似能力。
- lexical fallback 高分不等于模型服务下的正式质量。
- 生产评测还需要真实查询分布、独立标注者一致性、来源逐条法律复核、模型漂移和线上延迟/可用性测试。
