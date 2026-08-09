# 11 阶段1数据库设计

SQLite + SQLAlchemy 2 ORM，初始迁移为 alembic/versions/20260801_initial.py。表包括 users、properties、user_property_bindings、work_orders、work_order_events、work_order_ratings、announcements、bills、payment_records、bill_review_requests、inspection_tasks、inspection_records、rectification_orders、audit_logs。UUID 主键；外键关联；对外编号唯一；金额为 Numeric(12,2)；UTC datetime；重要记录不提供物理删除 API。关系主线：用户—绑定—房屋—工单/账单，工单—事件/评价，巡检任务—记录—整改。

