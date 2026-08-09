# 07 开源项目调研

| 项目 | 仓库 | 调研日期 | Commit/版本 | 许可证 | 参考内容 | 是否复制代码 | 实际采用方式 |
|---|---|---|---|---|---|---|---|
| Condo | https://github.com/open-condo-software/condo | 2026-08-01 | 未固定（网络克隆重置） | MIT（仓库 LICENSE 记录） | 房屋-住户关系、服务记录层级 | 否 | 独立设计 SQLAlchemy 实体 |
| Atlas CMMS | https://github.com/Grashjs/cmms | 2026-08-01 | 未固定（网络克隆重置） | AGPL-3.0（仓库 LICENSE 记录） | 工单优先级、派单、时间线概念 | 否 | 仅借鉴业务概念，未复制代码 |
| FastAPI Full Stack Template | https://github.com/fastapi/full-stack-fastapi-template | 2026-08-01 | 未固定 | MIT（仓库 LICENSE 记录） | 认证、分层、健康检查思路 | 否 | 采用 FastAPI/JWT 的独立小型实现 |

临时克隆仅位于项目外部；因网络重置未将外部仓库保留或复制进本项目。
# 阶段 3 增补（2026-08-02）

| 项目 | 仓库 | 使用版本范围 | 许可证 | 使用方式 |
|---|---|---|---|---|
| LangGraph | https://github.com/langchain-ai/langgraph | `>=1.2,<1.3`（本地验证 1.2.10） | MIT | 直接依赖；使用 StateGraph、interrupt/Command 和 SQLite checkpointer；未复制教程代码 |
| langgraph-checkpoint-sqlite | https://pypi.org/project/langgraph-checkpoint-sqlite/ | `>=3.1,<4` | MIT | 直接依赖；保存会话流程 checkpoint |

调研依据为 LangGraph 官方中断文档与官方仓库 LICENSE；未引入其他 Agent 框架、LangGraph Cloud 或 LangSmith 运行时依赖。

## Stage 5 supplement (2026-08-05)

| Project | Repository | Observed release/version | License | Adoption |
|---|---|---:|---|---|
| Playwright Python | https://github.com/microsoft/playwright-python | v1.61.0 | Apache-2.0 | Optional dev dependency; browser E2E/traces/screenshots only; no copied code |
| Locust | https://github.com/locustio/locust | 2.44.0 | MIT | Design reference only; not introduced |
| Promptfoo | https://github.com/promptfoo/promptfoo | 0.121.15 | MIT | Design reference only; deterministic tests retained |
| Ragas | https://github.com/vibrantlabsai/ragas | main checked 2026-08-05 | Apache-2.0 | Design reference only; not introduced |
| Trivy | https://github.com/aquasecurity/trivy | current CLI when installed | Apache-2.0 | Optional scanner, not bundled |

Versions and licenses were checked from the upstream GitHub repository/release or LICENSE information on the date above. No source code from these repositories has been copied into this project.
