# 阶段 3 基线问题

- 2026-08-02：仓库 `.venv` 的 Python 3.13.14 未安装项目依赖，无法执行 pytest、Alembic 或 RAG 脚本。系统 Python 3.14 环境具备依赖并实际运行了阶段 1/2 的 9 项测试。该问题不改变代码逻辑；按 README 的 `python -m pip install -e ".[dev]"` 可重建可用环境。
- 系统 Python 3.14 运行会输出第三方库与项目中既有 `datetime.utcnow()` 弃用警告；本阶段没有将其误报为测试失败。
