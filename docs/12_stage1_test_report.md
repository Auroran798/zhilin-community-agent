# 12 阶段1测试报告

执行时间：2026-08-01；命令：python -m pytest 和 python -m pytest --cov=api --cov=domain --cov=data --cov-report=term。

| 项目 | 实际结果 |
|---|---|
| 测试总数 | 6 |
| 通过 | 6 |
| 失败 | 0 |
| 跳过 | 0 |
| 覆盖率 | 89%（583 statements，63 missed；2026-08-01 实测） |
| 外部网络 | 未依赖 |
| 已知警告 | Python 3.14 对 datetime.utcnow 的弃用警告；FastAPI 路由兼容警告 |

已新增每例独立临时 SQLite 数据库的集成测试，并加入可重复 Seed 的独立数据库测试；覆盖完整工单闭环和巡检整改闭环。总体覆盖率已超过80%目标。Python 3.14 仍报告 UTC 时间弃用警告。
