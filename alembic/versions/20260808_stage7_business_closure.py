"""Stage 7 business closure and historical metadata reconciliation.

The first project migration used ``Base.metadata.create_all``.  Consequently
some later ORM indexes were not represented in an immutable revision even
though production/demo databases had already reached Stage 6.  This migration
adds the actual Stage 7 schema and reconciles those two omitted observability
indexes without altering any historical revision.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260808_stage7_business_closure"
down_revision = "20260807_stage6_public_real"
branch_labels = None
depends_on = None


NEW_TABLES = (
    "sla_policies", "maintenance_profiles", "maintenance_skills",
    "maintenance_profile_skills", "announcement_approvals", "notifications",
    "inspection_plans", "equipment", "bill_items", "scheduler_job_runs",
)


def _columns(bind, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table)}


def _foreign_keys(bind, table: str) -> set[tuple[tuple[str, ...], str]]:
    return {(tuple(key["constrained_columns"]), key["referred_table"]) for key in sa.inspect(bind).get_foreign_keys(table)}


def _create_new_tables(bind) -> None:
    inspector=sa.inspect(bind)
    if not inspector.has_table("sla_policies"):
        op.create_table("sla_policies",sa.Column("id",sa.String(36),primary_key=True),sa.Column("name",sa.String(100),nullable=False,unique=True),sa.Column("category",sa.String(32)),sa.Column("risk_level",sa.String(16)),sa.Column("response_minutes",sa.Integer(),nullable=False),sa.Column("processing_minutes",sa.Integer(),nullable=False),sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
        for column in ("category","risk_level","enabled"):op.create_index(f"ix_sla_policies_{column}","sla_policies",[column])
    if not inspector.has_table("maintenance_profiles"):
        op.create_table("maintenance_profiles",sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),primary_key=True),sa.Column("employee_code",sa.String(32),nullable=False),sa.Column("display_name",sa.String(80),nullable=False),sa.Column("service_area",sa.String(200),nullable=False,server_default="all"),sa.Column("availability_status",sa.String(16),nullable=False,server_default="available"),sa.Column("current_workload",sa.Integer(),nullable=False,server_default="0"),sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
        for column in ("employee_code","availability_status","enabled"):op.create_index(f"ix_maintenance_profiles_{column}","maintenance_profiles",[column],unique=column=="employee_code")
    if not inspector.has_table("maintenance_skills"):
        op.create_table("maintenance_skills",sa.Column("code",sa.String(32),primary_key=True),sa.Column("name",sa.String(80),nullable=False,unique=True),sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.true()))
    if not inspector.has_table("maintenance_profile_skills"):
        op.create_table("maintenance_profile_skills",sa.Column("profile_user_id",sa.String(36),sa.ForeignKey("maintenance_profiles.user_id"),primary_key=True),sa.Column("skill_code",sa.String(32),sa.ForeignKey("maintenance_skills.code"),primary_key=True))
    if not inspector.has_table("announcement_approvals"):
        op.create_table("announcement_approvals",sa.Column("id",sa.String(36),primary_key=True),sa.Column("announcement_id",sa.String(36),sa.ForeignKey("announcements.id"),nullable=False),sa.Column("requested_by",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("reviewed_by",sa.String(36),sa.ForeignKey("users.id")),sa.Column("decision",sa.String(16),nullable=False,server_default="pending"),sa.Column("review_comment",sa.Text()),sa.Column("requested_at",sa.DateTime(timezone=True),nullable=False),sa.Column("reviewed_at",sa.DateTime(timezone=True)))
        for column in ("announcement_id","requested_by","reviewed_by","decision"):op.create_index(f"ix_announcement_approvals_{column}","announcement_approvals",[column])
    if not inspector.has_table("notifications"):
        op.create_table("notifications",sa.Column("id",sa.String(36),primary_key=True),sa.Column("recipient_user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("notification_type",sa.String(48),nullable=False),sa.Column("title",sa.String(160),nullable=False),sa.Column("content",sa.Text(),nullable=False),sa.Column("business_type",sa.String(40),nullable=False),sa.Column("business_id",sa.String(36),nullable=False),sa.Column("status",sa.String(12),nullable=False,server_default="unread"),sa.Column("idempotency_key",sa.String(200),nullable=False,unique=True),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("read_at",sa.DateTime(timezone=True)))
        for column in ("recipient_user_id","notification_type","business_type","business_id","status","created_at"):op.create_index(f"ix_notifications_{column}","notifications",[column])
    if not inspector.has_table("inspection_plans"):
        op.create_table("inspection_plans",sa.Column("id",sa.String(36),primary_key=True),sa.Column("name",sa.String(120),nullable=False,unique=True),sa.Column("category",sa.String(32),nullable=False),sa.Column("target_type",sa.String(32),nullable=False),sa.Column("target_id",sa.String(36)),sa.Column("frequency",sa.String(16),nullable=False),sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("assigned_role",sa.String(32),nullable=False,server_default="maintenance"),sa.Column("assignee_id",sa.String(36),sa.ForeignKey("users.id")),sa.Column("next_run_at",sa.DateTime(timezone=True),nullable=False),sa.Column("created_by",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
        for column in ("category","target_id","frequency","enabled","assignee_id","next_run_at"):op.create_index(f"ix_inspection_plans_{column}","inspection_plans",[column])
    if not inspector.has_table("equipment"):
        op.create_table("equipment",sa.Column("id",sa.String(36),primary_key=True),sa.Column("equipment_code",sa.String(48),nullable=False),sa.Column("name",sa.String(120),nullable=False),sa.Column("category",sa.String(32),nullable=False),sa.Column("property_id",sa.String(36),sa.ForeignKey("properties.id")),sa.Column("location",sa.String(200),nullable=False),sa.Column("manufacturer",sa.String(100)),sa.Column("model",sa.String(100)),sa.Column("installed_at",sa.DateTime(timezone=True)),sa.Column("status",sa.String(16),nullable=False,server_default="normal"),sa.Column("last_inspection_at",sa.DateTime(timezone=True)),sa.Column("next_inspection_at",sa.DateTime(timezone=True)),sa.Column("enabled",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
        for column in ("equipment_code","name","category","property_id","location","status","enabled"):op.create_index(f"ix_equipment_{column}","equipment",[column],unique=column=="equipment_code")
    if not inspector.has_table("bill_items"):
        op.create_table("bill_items",sa.Column("id",sa.String(36),primary_key=True),sa.Column("bill_id",sa.String(36),sa.ForeignKey("bills.id"),nullable=False),sa.Column("item_type",sa.String(32),nullable=False),sa.Column("item_name",sa.String(120),nullable=False),sa.Column("amount",sa.Numeric(12,2),nullable=False),sa.Column("quantity",sa.Numeric(12,2)),sa.Column("unit_price",sa.Numeric(12,2)),sa.Column("description",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
        op.create_index("ix_bill_items_bill_id","bill_items",["bill_id"]);op.create_index("ix_bill_items_item_type","bill_items",["item_type"])
    if not inspector.has_table("scheduler_job_runs"):
        op.create_table("scheduler_job_runs",sa.Column("id",sa.String(36),primary_key=True),sa.Column("job_name",sa.String(64),nullable=False),sa.Column("run_key",sa.String(100),nullable=False,unique=True),sa.Column("status",sa.String(16),nullable=False,server_default="completed"),sa.Column("result_json",sa.Text()),sa.Column("error_message",sa.Text()),sa.Column("started_at",sa.DateTime(timezone=True),nullable=False),sa.Column("finished_at",sa.DateTime(timezone=True)))
        op.create_index("ix_scheduler_job_runs_job_name","scheduler_job_runs",["job_name"])


def _batch_options(bind) -> dict[str, str]:
    # SQLite needs table recreation for foreign keys and unique constraints;
    # PostgreSQL can alter in place. Recreating a PostgreSQL table would drop
    # its primary key while freshly-created Stage 7 foreign keys depend on it.
    return {"recreate": "always"} if bind.dialect.name == "sqlite" else {}


def upgrade():
    bind = op.get_bind()
    _create_new_tables(bind)

    announcement_columns = _columns(bind, "announcements")
    if not {"target_type", "target_building_no", "summary", "suggested_publish_time", "scheduled_publish_at"}.issubset(announcement_columns):
        with op.batch_alter_table("announcements", **_batch_options(bind)) as batch:
            if "target_type" not in announcement_columns:
                batch.add_column(sa.Column("target_type", sa.String(16), nullable=False, server_default="all"))
            if "target_building_no" not in announcement_columns:
                batch.add_column(sa.Column("target_building_no", sa.String(12), nullable=True))
            if "summary" not in announcement_columns:
                batch.add_column(sa.Column("summary", sa.Text(), nullable=True))
            if "suggested_publish_time" not in announcement_columns:
                batch.add_column(sa.Column("suggested_publish_time", sa.DateTime(timezone=True), nullable=True))
            if "scheduled_publish_at" not in announcement_columns:
                batch.add_column(sa.Column("scheduled_publish_at", sa.DateTime(timezone=True), nullable=True))
    for name, columns in (("ix_announcements_target_type", ["target_type"]), ("ix_announcements_target_building_no", ["target_building_no"]), ("ix_announcements_scheduled_publish_at", ["scheduled_publish_at"])):
        if name not in _indexes(bind, "announcements"):
            op.create_index(name, "announcements", columns)

    work_columns = _columns(bind, "work_orders")
    work_fks = _foreign_keys(bind, "work_orders")
    required_work_columns = {"equipment_id", "sla_policy_id", "response_deadline", "processing_deadline", "first_response_at", "sla_response_status", "sla_processing_status", "overdue_at"}
    if not required_work_columns.issubset(work_columns) or (("equipment_id",), "equipment") not in work_fks or (("sla_policy_id",), "sla_policies") not in work_fks:
        with op.batch_alter_table("work_orders", **_batch_options(bind)) as batch:
            if "equipment_id" not in work_columns: batch.add_column(sa.Column("equipment_id", sa.String(36), nullable=True))
            if "sla_policy_id" not in work_columns: batch.add_column(sa.Column("sla_policy_id", sa.String(36), nullable=True))
            if "response_deadline" not in work_columns: batch.add_column(sa.Column("response_deadline", sa.DateTime(timezone=True), nullable=True))
            if "processing_deadline" not in work_columns: batch.add_column(sa.Column("processing_deadline", sa.DateTime(timezone=True), nullable=True))
            if "first_response_at" not in work_columns: batch.add_column(sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True))
            if "sla_response_status" not in work_columns: batch.add_column(sa.Column("sla_response_status", sa.String(16), nullable=False, server_default="normal"))
            if "sla_processing_status" not in work_columns: batch.add_column(sa.Column("sla_processing_status", sa.String(16), nullable=False, server_default="normal"))
            if "overdue_at" not in work_columns: batch.add_column(sa.Column("overdue_at", sa.DateTime(timezone=True), nullable=True))
            if (("equipment_id",), "equipment") not in work_fks: batch.create_foreign_key("fk_work_orders_equipment", "equipment", ["equipment_id"], ["id"])
            if (("sla_policy_id",), "sla_policies") not in work_fks: batch.create_foreign_key("fk_work_orders_sla_policy", "sla_policies", ["sla_policy_id"], ["id"])
    for name, columns in (("ix_work_orders_equipment_id", ["equipment_id"]), ("ix_work_orders_sla_policy_id", ["sla_policy_id"]), ("ix_work_orders_response_deadline", ["response_deadline"]), ("ix_work_orders_processing_deadline", ["processing_deadline"]), ("ix_work_orders_sla_response_status", ["sla_response_status"]), ("ix_work_orders_sla_processing_status", ["sla_processing_status"])):
        if name not in _indexes(bind, "work_orders"):
            op.create_index(name, "work_orders", columns)

    task_columns = _columns(bind, "inspection_tasks")
    task_fks = _foreign_keys(bind, "inspection_tasks")
    task_unique = {tuple(item.get("column_names", [])) for item in sa.inspect(bind).get_unique_constraints("inspection_tasks")}
    if not {"plan_id", "period_key", "equipment_id"}.issubset(task_columns) or (("plan_id",), "inspection_plans") not in task_fks or (("equipment_id",), "equipment") not in task_fks or ("plan_id", "period_key") not in task_unique:
        with op.batch_alter_table("inspection_tasks", **_batch_options(bind)) as batch:
            if "plan_id" not in task_columns: batch.add_column(sa.Column("plan_id", sa.String(36), nullable=True))
            if "period_key" not in task_columns: batch.add_column(sa.Column("period_key", sa.String(16), nullable=True))
            if "equipment_id" not in task_columns: batch.add_column(sa.Column("equipment_id", sa.String(36), nullable=True))
            if (("plan_id",), "inspection_plans") not in task_fks: batch.create_foreign_key("fk_inspection_tasks_plan", "inspection_plans", ["plan_id"], ["id"])
            if (("equipment_id",), "equipment") not in task_fks: batch.create_foreign_key("fk_inspection_tasks_equipment", "equipment", ["equipment_id"], ["id"])
            if ("plan_id", "period_key") not in task_unique: batch.create_unique_constraint("uq_inspection_task_plan_period", ["plan_id", "period_key"])
    for name, columns in (("ix_inspection_tasks_plan_id", ["plan_id"]), ("ix_inspection_tasks_equipment_id", ["equipment_id"])):
        if name not in _indexes(bind, "inspection_tasks"):
            op.create_index(name, "inspection_tasks", columns)

    rect_columns = _columns(bind, "rectification_orders")
    rect_fks = _foreign_keys(bind, "rectification_orders")
    if "equipment_id" not in rect_columns or (("equipment_id",), "equipment") not in rect_fks:
        with op.batch_alter_table("rectification_orders", **_batch_options(bind)) as batch:
            if "equipment_id" not in rect_columns: batch.add_column(sa.Column("equipment_id", sa.String(36), nullable=True))
            if (("equipment_id",), "equipment") not in rect_fks: batch.create_foreign_key("fk_rectification_orders_equipment", "equipment", ["equipment_id"], ["id"])
    if "ix_rectification_orders_equipment_id" not in _indexes(bind, "rectification_orders"):
        op.create_index("ix_rectification_orders_equipment_id", "rectification_orders", ["equipment_id"])

    # These indexes existed in the desired ORM contract but were omitted from
    # the old dynamic baseline on databases upgraded before Stage 4.
    for table, name, columns in (("execution_traces", "ix_execution_traces_parent_trace_id", ["parent_trace_id"]), ("harness_executions", "ix_harness_executions_error_code", ["error_code"])):
        if name not in _indexes(bind, table):
            op.create_index(name, table, columns)


def downgrade():
    bind = op.get_bind()
    for table,name in (("execution_traces","ix_execution_traces_parent_trace_id"),("harness_executions","ix_harness_executions_error_code")):
        if name in _indexes(bind,table):op.drop_index(name,table_name=table)
    if "equipment_id" in _columns(bind,"rectification_orders"):
        if "ix_rectification_orders_equipment_id" in _indexes(bind,"rectification_orders"):op.drop_index("ix_rectification_orders_equipment_id",table_name="rectification_orders")
        with op.batch_alter_table("rectification_orders",**_batch_options(bind)) as batch:batch.drop_column("equipment_id")
    task_columns=_columns(bind,"inspection_tasks")
    for name in ("ix_inspection_tasks_plan_id","ix_inspection_tasks_equipment_id"):
        if name in _indexes(bind,"inspection_tasks"):op.drop_index(name,table_name="inspection_tasks")
    with op.batch_alter_table("inspection_tasks",**_batch_options(bind)) as batch:
        for column in ("equipment_id","period_key","plan_id"):
            if column in task_columns:batch.drop_column(column)
    work_columns=_columns(bind,"work_orders")
    for name in ("ix_work_orders_equipment_id","ix_work_orders_sla_policy_id","ix_work_orders_response_deadline","ix_work_orders_processing_deadline","ix_work_orders_sla_response_status","ix_work_orders_sla_processing_status"):
        if name in _indexes(bind,"work_orders"):op.drop_index(name,table_name="work_orders")
    with op.batch_alter_table("work_orders",**_batch_options(bind)) as batch:
        for column in ("overdue_at","sla_processing_status","sla_response_status","first_response_at","processing_deadline","response_deadline","sla_policy_id","equipment_id"):
            if column in work_columns:batch.drop_column(column)
    announcement_columns=_columns(bind,"announcements")
    for name in ("ix_announcements_target_type","ix_announcements_target_building_no","ix_announcements_scheduled_publish_at"):
        if name in _indexes(bind,"announcements"):op.drop_index(name,table_name="announcements")
    with op.batch_alter_table("announcements",**_batch_options(bind)) as batch:
        for column in ("scheduled_publish_at","suggested_publish_time","summary","target_building_no","target_type"):
            if column in announcement_columns:batch.drop_column(column)
    for name in reversed(NEW_TABLES):
        if sa.inspect(bind).has_table(name):
            op.drop_table(name)
