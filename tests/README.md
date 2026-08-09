# tests

测试覆盖阶段 1–7 的状态机、RBAC、RAG、Agent、MCP/Harness、故障恢复、迁移和公开数据边界。`tests/conftest.py` 为每次会话隔离数据库、文件、Chroma 与 Agent checkpoint；浏览器 E2E、并发烟测和安全扫描由 `scripts/` 下独立入口执行。
