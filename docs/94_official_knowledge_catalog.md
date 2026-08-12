# 官方知识目录与许可边界

更新日期：2026-08-10

## 当前规模

| 类别 | 数量 | 状态 |
|---|---:|---|
| 真实官方材料 | 28 | 已登记、审核、索引并激活 |
| Demo 合成制度 | 6 | 仅限 Demo Garden；引用明确标注 synthetic |
| 可由下载白名单重建的官方快照 | 22 | HTTPS 精确主机、MIME/签名、大小、SHA-256 与 manifest 校验 |
| 当前激活知识切块 | 1,573 | 由 34 份文档解析生成；保留文档版本、章节与可用页码 |
| RAG 固定回归用例 | 128 | 含 44 条新增中英官方来源与辖区冲突用例 |

## 来源覆盖

| 辖区 | 官方数量 | 主要内容 | 许可/使用边界 |
|---|---:|---|---|
| 中国全国 | 6 | 物业管理、维修资金、装修、高层建筑消防 | 政府网站公开发布；按全国现行版本回答 |
| 北京市 | 2 | 物业区域消防、DB11/T 751-2025 住宅物业服务 | 仅适用于北京 |
| 上海市 | 1 | 住宅小区应急预案示范文本 | 仅适用于上海 |
| 英国/英格兰社会住房 | 6 | Complaint Handling Code、Awaab's Law、投诉路径、监管分工、潮湿霉菌 | GOV.UK 内容按 OGL v3；Ombudsman 页面另行记录使用条款 |
| 澳大利亚新南威尔士州 | 5 | 租赁维修、strata 共用区域、投诉与调解 | NSW.gov.au 内容通常为 CC BY 4.0；保留例外声明 |
| 澳大利亚维多利亚州 | 2 | 紧急/非紧急维修与灾害建议 | Consumer Affairs Victoria 内容为 CC BY 4.0；排除标识和第三方材料 |
| 新西兰 | 5 | 维修责任、14 日整改、灾害、健康住宅、房东合规清单 | Crown copyright；仅按其条件作注明来源的非商业使用 |
| GLOBAL | 1 | Open311 GeoReport v2 接口规范 | 仅作为技术规范，不作为物业法律依据 |

逐条标题、官方 URL、发布者、版本、生效时间、许可、辖区、路径和审核状态见 `data/knowledge/source_registry.csv`；可重建批次的独立元数据见 `data/knowledge/official_source_metadata.csv`，下载白名单见 `data/knowledge/international_sources.csv`，逐源证明见 `data/knowledge/manifests/`。

## 回答硬规则

1. 查询先确定 jurisdiction，再过滤审核状态、可回答性、版本、有效期和权限。
2. 问题未选择辖区而知识库存在多个可用辖区时拒答。
3. 问题显式混入其他国家或城市时返回 `JURISDICTION_CONFLICT`，不进行跨辖区拼接。
4. 中文问题可用受控中英术语扩展召回英文原文；引用仍指向原始官方页面，不伪造翻译版本。
5. 公开投诉/违规业务记录只做研究统计，不被当作通用规则或当前个案事实。
6. 离线 hash/lexical 成绩只作为回归证据；真实多语种 embedding、外部 reranker 和 500 条以上独立金标仍是正式质量声明前提。

## 重建命令

```powershell
python scripts/sync_international_knowledge.py --refresh
python scripts/verify_source_registry.py
python scripts/import_knowledge.py
python evals/rag/run.py
python scripts/run_complete_acceptance.py --security
```
