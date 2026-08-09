# Stage 7 Scheduler

SchedulerService.run_due 可由单实例调度器或经理演示按钮触发，负责：巡检计划生成、SLA 扫描、整改到期提醒和已审批定时公告发布。scheduler_job_runs.run_key 防止同一分钟重复扫描；巡检任务另有计划+周期唯一约束。

当前 Demo 只支持单 Scheduler 实例，不引入 Celery、Kafka 或分布式锁。多实例部署需在未来增加数据库锁或外部协调后再启用。
