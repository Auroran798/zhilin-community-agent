# mcp_server

阶段 4 的物业 MCP Server，使用官方 `mcp` Python SDK 1.29.0（MIT）和 `FastMCP`。默认使用 stdio；工具会调用共享 Harness，再复用阶段 1—3 的业务服务，绝不复制业务逻辑。

启动前先迁移并准备受控开发身份：

```powershell
python -m alembic upgrade head
python -m data.seed
$env:MCP_DEV_AUTH_ENABLED="true"
$env:MCP_DEV_USER_ID="<resident_demo 的 UUID>"
python -m mcp_server.server
```

开发认证仅用于 stdio/Inspector，生产环境若启用会被拒绝。`MCP_DEV_WRITE_CONFIRMED=false` 时只能读取；写操作仍要有幂等键、服务端角色/对象权限和受控确认。没有 `publish_announcement`、`update_bill`、`refund` 或 `waive_fee` 工具。

可用工具包括上下文/权限、工单、账单只读比较、公告只读与送审、巡检任务、整改、`search_knowledge`/`ask_knowledge` 等；所有写工具都经过 Harness 确认、权限、幂等和审计。发布公告、修改账单、退款和减免工具不存在。

真实 CLI 协议检查：`python scripts/demo_mcp_flow.py`；失败恢复：`python scripts/demo_failure_recovery.py`。Inspector：`npx @modelcontextprotocol/inspector python -m mcp_server.server`（当前机器需另行安装 Node.js/npx，并传入相同开发环境变量）。
