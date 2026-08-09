# 阶段 6 基线问题记录

检查时间：2026-08-07（Asia/Shanghai）

在任何阶段 6 代码或数据变更之前，已尝试执行项目既有的全量测试和 Alembic 检查。当前工作区的 `.venv` 为 Python 3.13，但尚未安装项目依赖：

- `.venv\\Scripts\\python.exe -m pytest -q`：失败，`No module named pytest`。
- `.venv\\Scripts\\python.exe -m alembic upgrade head`：失败，当前安装方式不支持以模块入口启动 Alembic（`alembic.__main__` 不存在）。

这是依赖环境尚未按 `pyproject.toml` 安装造成的既有基线问题，并非阶段 6 功能回归。阶段 6 实现完成后已安装锁定范围内的项目依赖，`alembic upgrade head` 成功、数据库处于 `20260807_stage6_public_real (head)`，且全量 pytest 通过。

后续检查还发现一个既有迁移一致性问题：`alembic check` 会为早期 Agent、RAG 和 Harness 表报告大量未生成的升级操作（索引、可空性和唯一约束差异）。输出中没有 `public_datasets` 或 `public_cases`，因此阶段 6 新迁移本身未产生额外的模型/迁移漂移。此遗留问题未在本阶段重写，以免将阶段 0—5 的大范围模式重构混入真实数据接入；应在后续专门的 schema-baseline 维护任务中处理。
