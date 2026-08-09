"""Complete Stage 3 audit, review, confirmation and memory metadata."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision="20260802_stage3_full"
down_revision="20260802_stage3_agent"

def upgrade():
    inspector = inspect(op.get_bind())
    if inspector.has_table("agent_tool_calls"):
        return
    with op.batch_alter_table("agent_sessions") as b:
        b.add_column(sa.Column("session_no",sa.String(48),nullable=True));b.add_column(sa.Column("thread_id",sa.String(64),nullable=True));b.add_column(sa.Column("current_skill",sa.String(64)));b.add_column(sa.Column("current_intent",sa.String(64)));b.add_column(sa.Column("community_name",sa.String(100)));b.add_column(sa.Column("property_id",sa.String(36),sa.ForeignKey("properties.id", name="fk_agent_sessions_property_id")));b.add_column(sa.Column("closed_at",sa.DateTime()))
        b.create_unique_constraint("uq_agent_sessions_session_no",["session_no"]);b.create_unique_constraint("uq_agent_sessions_thread_id",["thread_id"])
    with op.batch_alter_table("agent_messages") as b:
        b.add_column(sa.Column("content_redacted",sa.Text()));b.add_column(sa.Column("message_type",sa.String(32),server_default="chat",nullable=False));b.add_column(sa.Column("tool_call_id",sa.String(36)))
    with op.batch_alter_table("agent_runs") as b:
        b.add_column(sa.Column("run_no",sa.String(48),nullable=True));b.add_column(sa.Column("intent_confidence",sa.Float()));b.add_column(sa.Column("active_skill",sa.String(64)));b.add_column(sa.Column("requires_manual_escalation",sa.Boolean(),server_default=sa.false(),nullable=False));b.add_column(sa.Column("llm_provider",sa.String(64)));b.add_column(sa.Column("llm_model",sa.String(128)));b.add_column(sa.Column("latency_ms",sa.Integer()));b.add_column(sa.Column("error_code",sa.String(64)));b.add_column(sa.Column("finished_at",sa.DateTime()))
        b.create_unique_constraint("uq_agent_runs_run_no",["run_no"])
    with op.batch_alter_table("agent_confirmations") as b:
        b.add_column(sa.Column("run_id",sa.String(36),sa.ForeignKey("agent_runs.id", name="fk_agent_confirmations_run_id")));b.add_column(sa.Column("action_type",sa.String(64)));b.add_column(sa.Column("cancelled_at",sa.DateTime()))
    with op.batch_alter_table("agent_memories") as b:
        b.add_column(sa.Column("memory_type",sa.String(80),server_default="preference",nullable=False));b.add_column(sa.Column("consented",sa.Boolean(),server_default=sa.true(),nullable=False));b.add_column(sa.Column("updated_at",sa.DateTime()));b.add_column(sa.Column("deleted_at",sa.DateTime()))
    with op.batch_alter_table("agent_staff_reviews") as b:
        b.add_column(sa.Column("review_no",sa.String(48),nullable=True));b.add_column(sa.Column("run_id",sa.String(36),sa.ForeignKey("agent_runs.id", name="fk_agent_staff_reviews_run_id")));b.add_column(sa.Column("review_type",sa.String(64),server_default="manual_service",nullable=False));b.add_column(sa.Column("summary",sa.Text()));b.add_column(sa.Column("assigned_to",sa.String(36),sa.ForeignKey("users.id", name="fk_agent_staff_reviews_assigned_to")));b.add_column(sa.Column("result",sa.Text()));b.add_column(sa.Column("handled_at",sa.DateTime()))
        b.create_unique_constraint("uq_agent_staff_reviews_review_no",["review_no"])
    op.create_table("agent_tool_calls",sa.Column("id",sa.String(36),primary_key=True),sa.Column("run_id",sa.String(36),sa.ForeignKey("agent_runs.id", name="fk_agent_tool_calls_run_id"),nullable=False),sa.Column("tool_name",sa.String(64),nullable=False),sa.Column("arguments_redacted",sa.Text()),sa.Column("idempotency_key",sa.String(100)),sa.Column("status",sa.String(24),nullable=False),sa.Column("result_summary",sa.Text()),sa.Column("error_code",sa.String(64)),sa.Column("latency_ms",sa.Integer()),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("finished_at",sa.DateTime()))
    op.create_index("ix_agent_tool_calls_run_id","agent_tool_calls",["run_id"]);op.create_index("ix_agent_tool_calls_tool_name","agent_tool_calls",["tool_name"])

def downgrade():
    op.drop_table("agent_tool_calls")
    # SQLite downgrade intentionally removes Stage 3 completion fields in reverse order.
    for table, columns in [("agent_staff_reviews",["handled_at","result","assigned_to","summary","review_type","run_id","review_no"]),("agent_memories",["deleted_at","updated_at","consented","memory_type"]),("agent_confirmations",["cancelled_at","action_type","run_id"]),("agent_runs",["finished_at","error_code","latency_ms","llm_model","llm_provider","requires_manual_escalation","active_skill","intent_confidence","run_no"]),("agent_messages",["tool_call_id","message_type","content_redacted"]),("agent_sessions",["closed_at","property_id","community_name","current_intent","current_skill","thread_id","session_no"])]:
        with op.batch_alter_table(table) as b:
            for col in columns: b.drop_column(col)
