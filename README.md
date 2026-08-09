# 智邻管家：物业社区管理智能体

> 面向物业社区管理场景的智能体应用原型 / 完整 Demo 系统。

智邻管家以一个虚拟小区为边界，演示居民、客服、维修/巡检和经理围绕报修、公告、费用、巡检四条物业业务线协作的完整闭环。它结合 FastAPI、SQLAlchemy/Alembic、Agent、RAG、MCP/Harness、PostgreSQL（可选）与 SQLite Demo，并保留脱敏的 NYC HPD 真实公开历史数据查询能力。

这不是已部署到真实物业公司的生产系统；不接入真实居民生产数据、支付、门禁、摄像头或 IoT，且不宣称商业生产级 SLA。

## v1.3.0 整改后能力

| 业务线 | 闭环能力 | 人工与安全边界 |
| --- | --- | --- |
| 报修 | Agent 采集信息、风险分级、建单、确定性 SLA、派单建议、人工派单、维修流转、居民确认/评价、完整时间线 | Agent 只能建议派单；状态机拒绝非法跳转 |
| 公告 | Agent 生成结构化草稿、定向范围、提交审核、人工批准、发布、站内通知和已读状态 | 草稿不能直接发布；发布不暴露给 MCP/Agent 自动调用 |
| 费用 | 本人账单、明细、支付历史、账单对比、差异解释、复核申请与人工处理 | 无修改账单、退款、减免或人工标记付款工具 |
| 巡检 | 巡检计划、幂等任务生成、任务执行、异常记录、整改、到期提醒、人工复查关闭 | critical/high 整改只能由经理人工复查关闭 |

此外提供设备台账及其关联工单/巡检/整改历史、统一通知中心、经理 Dashboard、审计日志、MCP 工具目录与 Harness 调用链。

## 架构与数据边界

```text
Streamlit Web / FastAPI API
          │
Agent（Fake LLM 或兼容 LLM） ─ Skills ─ MCP/Harness
          │                           │
业务服务（SLA、RBAC、审批、审计、Scheduler）─ Outbox Worker
          │
SQLite Demo / PostgreSQL ─ RAG 知识库 ─ Public Real（只读、脱敏、独立）
```

- 业务金额、SLA 截止时间、逾期判断、账单对比、收件人范围和派单排序均由确定性服务层计算，LLM 只负责理解与表述。
- Public Real 是 NYC HPD 历史公开监管记录，不计入当前 Demo 小区的工单和 Dashboard 指标，不能被写入或修改。
- 写操作要求 RBAC、参数校验、幂等键、审计；Agent 写入还必须经过受信任的显式确认节点。
- 幂等键按“用户 + 操作 + 请求摘要”持久化；公告发布与 RAG 索引通过可重试 Outbox 解耦，索引故障不会回滚已发布业务状态。
- 系统统一使用 timezone-aware UTC 新写入；`as_utc` 兼容既有 SQLite 的无时区历史值。
- Chroma 固定为 0.6.3；1.0.0–1.5.9 命中 Critical CVE-2026-45829 且当前无修复版本。

## 快速开始

推荐 Python 3.12 或 3.13。Python 3.14 仅用于当前开发环境，部分第三方原生包可能有兼容性警告。

```powershell
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m data.seed
python -m uvicorn api.main:app --reload
# 另开终端
streamlit run web/app.py
```

访问：API 文档 <http://127.0.0.1:8000/docs>；Web <http://127.0.0.1:8501>。

Demo 账号：`resident_demo`、`service_demo`、`maintenance_demo`、`manager_demo`；密码均为 `DemoPass123!`。仅限本地演示。

## 验证与运行模式

```powershell
# 模型/迁移一致性与完整回归
python -m alembic check
python -m alembic upgrade head
python scripts/run_test_suite.py
python evals/stage5/run.py
python scripts/run_performance_baseline.py
python scripts/run_e2e.py
python scripts/run_security_scan.py

# 服务与 MCP
python -m uvicorn api.main:app
python -m mcp_server.server

# 容器（需要 Docker Desktop）
docker compose up --build -d
```

安全脚本会对部署依赖、源码配置和已构建的 `zhilin-community-agent-api` 镜像执行扫描，并生成 CycloneDX SBOM；`FAIL` 或 `NOT_RUN` 都会阻断发布。

默认 `DATA_MODE=demo` 使用合成小区数据。`DATA_MODE=public_real` 仅向客服/经理开放脱敏 NYC HPD 历史案例；不允许把公开案例转写为小区业务数据。

## 关键接口

- `GET /api/v1/work-orders/{id}/sla`、`GET /api/v1/work-orders/{id}/assignee-recommendation`
- `POST /api/v1/announcements/{id}/submit-review|approve|publish`
- `GET /api/v1/notifications`、`POST /api/v1/notifications/{id}/read`
- `GET /api/v1/bills/{id}/details`、`GET /api/v1/bills/{id}/compare/{previous_id}`
- `POST /api/v1/inspection-plans`、`POST /api/v1/scheduler/run-due`
- `GET /api/v1/equipment`、`GET /api/v1/equipment/{id}/history`

MCP/Harness 提供受权限保护的查询、建单、派单、审批申请、巡检和整改工具。为了沿用既有的安全承诺，`publish_announcement` 只保留在经理人工 API 工作流中，不向 MCP/Agent 自动公开。

## 文档与演示

- [阶段 7 架构](docs/72_stage7_architecture.md)
- [安全与权限矩阵](docs/81_stage7_security.md)
- [测试报告](docs/83_stage7_test_report.md)
- [8–12 分钟 Demo 脚本](docs/84_stage7_demo_script.md)
- [阶段 7 完成报告](docs/85_stage7_completion_report.md)

阶段 0–6 的历史文档、RAG 资料、公开数据来源及 Stage 5/6 交付证据均保留在 `docs/`、`data/` 与 `artifacts/`，并未因阶段 7 改写。
