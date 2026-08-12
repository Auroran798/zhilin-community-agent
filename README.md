# 智邻管家：北京物业社区管理智能体

智邻管家现以北京为默认业务辖区，是一个“北京国内物业业务为主、国际比较研究为辅”的完整演示与研究系统。系统保留原有报修、公告、账单、巡检、设备、RBAC、审计、MCP/Harness、RAG 和公开数据研究能力，但不会声称已经接入真实物业公司、真实居民、真实账单或真实小区工单。

## 三种产品模式

| 模式 | 默认检索范围 | 用途与限制 |
| --- | --- | --- |
| `domestic_beijing` | 全国 → 北京市；有当前小区上下文时再加入当前小区 | 默认模式；外国资料在检索前即被隔离 |
| `international_research` | 用户明确选择的单一外国 `jurisdiction` | 只用于制度比较和流程借鉴，不构成北京处理依据 |
| `demo_garden` | 全国 → 北京市 → Demo Garden | 演示合成小区的合同、规约、账单和业务流程 |

全国问题只检索全国资料；北京问题使用全国与北京适用链；“我们小区”问题必须有当前小区上下文。小区合同、规约和收费约定会明确标为社区层规则，不能描述成普遍法律；发生冲突时按上位法优先。混入多个城市/国家、来源失效、证据不足、越权、具体赔偿/减费/改账/法律责任承诺等请求会被拒绝或要求补充信息。

前端、Agent/API 响应、查询日志和引用均显示当前模式。`GET /api/v1/product-context` 可查看默认模式、辖区和三层适用范围。

## 数据边界

| 数据类 | 内容 | 是否可作个案事实 | 是否可作规则依据 |
| --- | --- | ---: | ---: |
| `KB_POLICY` | 全国与北京官方法律、法规、标准、指南、示范文本 | 否 | 是，须通过治理、有效期和辖区过滤 |
| `OPS_PUBLIC` | 12345 年度统计、政府报告等聚合数据 | 否 | 否，只用于类别与趋势分析 |
| `DEMO_SYNTHETIC` | 合成居民/业务标识、工单、投诉、巡检、设备、账单、公告和 SLA | 仅作演示 | 仅合成小区制度可作该 Demo 的社区层依据 |

当前统一来源注册表有 82 项。北京适用链内有 56 项全国/北京市来源，其中 54 项已审核、有效且 `answerable=true`；另外 2 项保持 `pending/answerable=false`。本阶段北京官方同步批次有 52 项候选，51 项下载成功，50 项可回答。完整数字和失败原因见 [北京官方知识目录](docs/95_beijing_official_knowledge_catalog.md)。

合成业务集固定种子生成 6,000 条记录，覆盖 2025-02-01 至 2026-08-01，共 546 天。数据不含真实姓名、电话、身份证、精确住址或真实物业公司事实。数据卡见 [北京数据卡](docs/96_beijing_data_card.md)。

## RAG 与 Agent

检索顺序为权限、模式/辖区、`answerable`、审核状态、有效期、当前版本前置过滤，再执行 BM25、Dense、RRF、每文档候选保护、文档级去重和可选外部 reranker。回答引用展示来源层级、地域、版本、生效/失效时间、官方 URL、章节/条款/页码和数据类。

当前环境没有真实多语种 embedding 服务和外部 reranker，因此质量模式是 `offline_fallback`。hash embedding 和 lexical reranker 只支持确定性回归，不能证明正式多语种语义质量。

Agent 默认优先识别北京，但不会把所有无地域问题强行认定为北京。业务查询只读取 Demo 或未来明确授权的数据；写操作继续受 RBAC、参数校验、显式确认、幂等和审计保护。Agent 没有自动发布公告、减免费用、修改账单或认定法律责任的工具。

## 快速开始

推荐 Python 3.12 或 3.13。

```powershell
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m data.seed
python scripts/sync_beijing_knowledge.py
python scripts/verify_source_registry.py
python scripts/import_knowledge.py --reindex-all
python scripts/generate_beijing_synthetic_ops.py
python -m uvicorn api.main:app --reload
# 另开终端
streamlit run web/app.py
```

API 文档：<http://127.0.0.1:8000/docs>；Web：<http://127.0.0.1:8501>。

Demo 账号为 `resident_demo`、`service_demo`、`maintenance_demo`、`manager_demo`，密码均为 `DemoPass123!`，仅限本地演示。

北京来源下载器使用精确 HTTPS 主机白名单，逐跳验证重定向和最终主机，并检查 MIME、PDF/HTML 文件签名、大小与 SHA-256；每个来源都有独立 manifest。无法确认版本、效力或回答许可的项不会进入回答索引。

## 可复现验证

```powershell
# 数据和迁移
python scripts/verify_source_registry.py
python -m alembic upgrade head
python -m alembic current
python -m alembic check

# 完整测试与受控回归
python -m pytest -q --disable-warnings
python scripts/run_agent_eval.py
python evals/beijing/run_controlled.py
python evals/beijing/run_security_gate.py
python evals/rag/run.py
python scripts/run_security_scan.py

# 汇总验收；加入 --security 会重跑安全扫描
python scripts/run_complete_acceptance.py --security
```

自动生成的 360 条中英文受控用例明确标为“回归集，非独立人工金标”。128 条 RAG 固定集的结果同样不构成正式评测。详见 [RAG 评测报告](docs/97_beijing_rag_evaluation_report.md)、[Agent 评测报告](docs/98_beijing_agent_evaluation_report.md)和[安全报告](docs/99_beijing_security_report.md)。

## 原有功能与国际资料

原有报修全生命周期、公告人工审核发布、模拟账单复核、巡检整改、设备台账、通知中心、经理 Dashboard、审计日志和 Outbox 均保留。英国、澳大利亚、新西兰和 Open311 官方资料未删除，只能在 `international_research` 中按单一精确辖区检索。历史 NYC/国际公开数据能力继续作为隔离研究功能，不进入北京默认回答。

## 交付文档

- [最终完整解决方案](docs/101_beijing_complete_solution.md)
- [最终验收报告](docs/100_beijing_final_acceptance.md)
- [北京官方知识目录](docs/95_beijing_official_knowledge_catalog.md)
- [数据卡](docs/96_beijing_data_card.md)
- [RAG 评测报告](docs/97_beijing_rag_evaluation_report.md)
- [Agent 评测报告](docs/98_beijing_agent_evaluation_report.md)
- [安全报告](docs/99_beijing_security_report.md)

阶段 0–7 的历史文档和国际研究资料继续保留。旧的国际优先方案已由北京优先方案取代，但未删除其可复现实验资产。
