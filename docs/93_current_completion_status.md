# 智邻管家当前完成状态

更新日期：2026-08-10

## 已完成并可验证

- 合成小区的报修、公告、账单、巡检、整改、设备、通知和人工审核闭环。
- Agent、Skills、MCP/Harness、RBAC、幂等、审计、Outbox 与失败恢复基础能力。
- 知识文档地域隔离、版本历史、有效期、角色范围、注入拦截和证据不足拒答。
- 知识源治理字段：国家、地域、语言、可回答性、权威等级、许可证、隐私最小化、解析版本、审核状态、校验和与翻译溯源。
- BM25、Dense、RRF 融合以及可配置 HTTP 多语种 reranker；离线模式使用 lexical/hash fallback。
- 34 份登记知识文档：28 份真实官方材料与 6 份明确标注的 Demo 合成制度；官方材料覆盖中国全国/北京/上海、英国、澳大利亚新州/维州、新西兰和 Open311。
- 22 份可由精确 HTTPS 主机白名单重建的官方快照及逐源 SHA-256 manifest；许可、辖区、版本、有效期和审核状态进入引用元数据。
- 离线 fallback 的受控中英术语扩展、每文档候选保护和显式辖区冲突拒答；这些增强不改变正式语义模型门槛。
- 可复现的来源治理检查、完整测试、Agent 评测、RAG 评测和统一验收报告。

## 当前验证结果

- 自动化测试：以 `scripts/run_complete_acceptance.py` 的最新报告为准。
- 当前离线 RAG 集：128 条，其中新增 44 条中英官方来源与辖区冲突用例；Recall@5 1.000，MRR@5 0.963，引用正确率 1.000，引用完整率 1.000，拒答 F1 1.000，地域泄漏 0。
- 上述 RAG 数字来自 `hashing-v1 + lexical reranker`，仅用于确定性回归，不是正式多语种语义模型成绩。
- 最新统一验收（含安全）为 PASS：51 项测试、95 条 Agent 评测、迁移一致性、34 条来源治理、RAG 评测和安全门禁均无阻断；安全扫描为 0 High/Critical、0 依赖漏洞、0 secrets，并生成 CycloneDX SBOM。

## 尚不能宣称完成的部分

- 尚未配置 BGE-M3/Qwen3-Embedding 或等价真实多语种 embedding 服务。
- 尚未配置真实多语种 reranker 并完成同集消融对比。
- 尚未达到 500–1,000 条独立人工审阅金标；当前 128 条受控回归集不能替代正式金标。
- 100–250 份官方知识文档的研究规模目标尚未达到；当前真实官方材料为 28 份，不虚报规模。
- 安全扫描、SBOM 和依赖漏洞结果必须在目标发布环境再次执行，`NOT_RUN` 不能算通过。

这些限制会由评测脚本自动标记为 `offline_fallback` / `NOT_FORMAL`，系统不会把它们隐藏或写成已经完成。

## 一键验收

```powershell
python scripts/run_complete_acceptance.py

# 发布前增加安全扫描
python scripts/run_complete_acceptance.py --security

# 正式研究报告必须满足真实 embedding、外部 reranker 和至少 500 条金标
python scripts/run_complete_acceptance.py --require-formal-rag
```

统一报告输出到 `artifacts/acceptance/final_acceptance.json`。
