# 阶段 4 最终验收报告

执行日期：2026-08-05

## 自动化与协议验收

- `python -m pytest -q`：25 passed，0 failed。
- `python -m compileall -q api agent harness mcp_server scripts web`：通过。
- Alembic 当前版本：`20260803_stage4_mcp_harness (head)`。
- `python scripts/demo_mcp_flow.py`：官方 Python `ClientSession` 与 stdio MCP Server 握手成功，发现并调用了 28 个公开工具。
- `python scripts/demo_failure_recovery.py`：重试、写后未知结果幂等恢复与敏感字段脱敏均通过。
- 真实 `@modelcontextprotocol/inspector` 2.0.0 CLI：`tools/list` 返回 28 个工具，`tools/call get_bound_property` 返回 `isError=false`、`ok=true`；Web Inspector 页面与 `/api/config` 均为 HTTP 200。

## Docker 与 Compose 验收

- Docker Hub `python:3.12-slim` 已成功拉取，digest 为 `sha256:507285ff17cb1d1756d3711c7543e82188f7a3752c79a9b3a4f9320640390300`。
- 标准 Dockerfile 默认使用 `python:3.12-slim`；受限网络可用 `PYTHON_BASE_IMAGE=mcr.microsoft.com/azurelinux/base/python:3.12` 覆盖。
- 由于原工作目录含中文字符，Docker Desktop BuildKit 在直接 Compose 构建时会产生非 ASCII gRPC header。项目新增 `scripts/compose_ascii_worktree.ps1`：它只复制到脚本管理的 `C:\DockerBuild\zhilin-community-agent` ASCII 工作副本，不移动或覆盖原项目。
- 在该 ASCII 工作副本中，以下 Compose 构建均返回退出码 0：

  ```text
  docker compose -p zhilin-stage4-ascii-check build api web
  PYTHON_BASE_IMAGE=python:3.12-slim docker compose -p zhilin-stage4-dockerhub-check build api web
  ```

- 两套 Compose 栈均以独立端口启动并达到 API `healthy`：Alembic 迁移和种子数据执行成功；`/health=ok`、`/ready=ready`、`manager_demo` 登录、MCP 工具目录（28 个工具）以及 Streamlit Web HTTP 200 均通过。
- 验收容器和网络已停止并移除；不会占用项目默认端口。

## 可复现命令

从原项目目录执行（Windows PowerShell）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/compose_ascii_worktree.ps1 -Action build
powershell -ExecutionPolicy Bypass -File scripts/compose_ascii_worktree.ps1 -Action up
powershell -ExecutionPolicy Bypass -File scripts/compose_ascii_worktree.ps1 -Action down
```

`Makefile` 同时提供 `compose-build`、`compose-up`、`compose-down` 目标，供已安装 GNU Make 的环境使用。

也可直接指定 MCR 备用基础镜像：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/compose_ascii_worktree.ps1 -Action build -PythonBaseImage mcr.microsoft.com/azurelinux/base/python:3.12
```

## 结论

阶段 4 的 MCP、Harness、安全控制、可观测性、迁移、全量测试、真实 Inspector、Docker Hub 构建、MCR 备用构建、Compose 构建和 Compose 运行均已实际通过，不存在待完成的阶段 4 验收项。
