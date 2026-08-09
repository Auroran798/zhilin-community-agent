# 阶段 4：MCP、Harness 与可观测性架构

## 1. 总体边界

阶段 4 基于官方 Python MCP SDK（`mcp` 1.29.0）。服务端使用 `FastMCP`，开发与验收传输采用可审计的 stdio；客户端使用 `ClientSession` 与 `stdio_client`。生产环境仍应按部署需要评估 Streamable HTTP，但开发认证不会暴露到生产默认配置。

调用路径为：

```text
LangGraph → ToolGateway → Harness → agent.tools / Stage 1 Service
```

业务逻辑只保留一份，MCP 层负责协议适配。默认 `AGENT_TOOL_BACKEND=local`；启用 `mcp` 模式时必须显式打开客户端，只有 `MCP_ALLOW_LOCAL_FALLBACK=true` 才允许失败后回退本地实现。

## 2. Harness 固定顺序

```text
注册表 → 可信身份 → 角色/对象权限 → Pydantic 校验与注入过滤
→ 确认 → 幂等键 → 读操作有限重试 / 熔断 → 业务服务 → 脱敏 trace
```

写操作不盲目重试；`unknown_after_write` 通过原业务幂等键恢复。公告发布、账单修改、退款、减免等高风险工具均明确禁止隐式执行。

## 3. stdio 身份边界

stdio 验收必须同时提供 `MCP_DEV_AUTH_ENABLED=true` 与有效的 `MCP_DEV_USER_ID`。身份、角色和确认状态不是工具参数。生产环境启用开发认证会直接失败；公告发布、账单修改、退款及减免工具不在默认公开集合中。

## 4. 可观测性

本地持久化表包括 `execution_traces`、`execution_spans`、`harness_executions`。管理 API 包括：

```text
/api/v1/observability/traces
/api/v1/observability/traces/{trace_id}
/api/v1/observability/tool-calls
/api/v1/observability/security-events
/api/v1/observability/metrics
/api/v1/mcp/tools
/api/v1/mcp/status
```

参数和结果入库前会脱敏电话、token、password、secret 等敏感字段。

## 5. Inspector 实际验收

已使用真实 `@modelcontextprotocol/inspector` 2.0.0 完成 CLI 验收，而不是只保留示例命令。使用有效开发用户 ID 后：

```powershell
npx --yes @modelcontextprotocol/inspector --cli python -m mcp_server.server -- `
  --transport stdio --cwd "$PWD" `
  -e "MCP_DEV_AUTH_ENABLED=true" `
  -e "MCP_DEV_USER_ID=<valid-manager-id>" `
  --method tools/list --format json

npx --yes @modelcontextprotocol/inspector --cli python -m mcp_server.server -- `
  --transport stdio --cwd "$PWD" `
  -e "MCP_DEV_AUTH_ENABLED=true" `
  -e "MCP_DEV_USER_ID=<valid-manager-id>" `
  --method tools/call --tool-name get_bound_property --format json
```

两条命令均返回成功；`tools/list` 返回 28 个工具，`tools/call` 返回 `ok=true`。Web Inspector 也已启动并通过 `http://localhost:6274/api/config` 返回 HTTP 200。

## 6. Docker 运行边界

`Dockerfile` 与 Compose 支持 `PYTHON_BASE_IMAGE` 覆盖，默认使用 Docker Hub 的 `python:3.12-slim`；受限网络可传入 MCR 基础镜像。对于 Windows 的非 ASCII 工作路径，使用 `scripts/compose_ascii_worktree.ps1` 创建脚本管理的 ASCII 构建副本后执行 Compose。镜像构建后必须执行 Alembic、种子数据、`/health`、`/ready` 和 MCP 管理 API 验收。
