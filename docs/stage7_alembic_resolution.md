# Stage 7 Alembic 漂移处理说明

## 结论

已解决。python -m alembic upgrade head 与 python -m alembic check 均通过。

## 根因

阶段 1 初始迁移历史上调用了 Base.metadata.create_all()。该方式会随运行时 ORM 元数据变化，无法作为不可变 schema 快照；后续部分 ORM 索引未在已经升级的 Stage 6 数据库中实际创建，从而导致 alembic check 报告漂移。

## 修复

新增 20260808_stage7_business_closure，不修改、不删除任何历史迁移。该迁移：

- 创建 Stage 7 的 SLA、维修人员、通知、巡检计划、设备、账单明细和调度运行表；
- 为既有工单、公告、巡检任务和整改工单补充 Stage 7 字段、索引和外键；
- 补齐历史遗漏的 execution_traces.parent_trace_id 与 harness_executions.error_code 索引；
- 对已存在的表/字段使用检查，兼容已有 Demo 库和新建库。

迁移历史的动态基线是既有技术债；后续迁移必须显式描述 schema 变化，不再扩大该模式。
