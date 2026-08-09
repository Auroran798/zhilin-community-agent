"""Stage 3 agent conversations, confirmations, audit summaries and memory."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision="20260802_stage3_agent"
down_revision="20260801_stage2_completion"

def upgrade():
    inspector = inspect(op.get_bind())
    if inspector.has_table("agent_sessions"):
        return
    op.create_table("agent_sessions",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("status",sa.String(24),nullable=False),sa.Column("follow_up_rounds",sa.Integer(),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("updated_at",sa.DateTime(),nullable=False))
    op.create_index("ix_agent_sessions_user_id","agent_sessions",["user_id"])
    op.create_table("agent_messages",sa.Column("id",sa.String(36),primary_key=True),sa.Column("session_id",sa.String(36),sa.ForeignKey("agent_sessions.id"),nullable=False),sa.Column("role",sa.String(16),nullable=False),sa.Column("content",sa.Text(),nullable=False),sa.Column("metadata_json",sa.Text()),sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_index("ix_agent_messages_session_id","agent_messages",["session_id"])
    op.create_table("agent_confirmations",sa.Column("id",sa.String(36),primary_key=True),sa.Column("session_id",sa.String(36),sa.ForeignKey("agent_sessions.id"),nullable=False),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("action",sa.String(64),nullable=False),sa.Column("preview_json",sa.Text(),nullable=False),sa.Column("status",sa.String(24),nullable=False),sa.Column("idempotency_key",sa.String(100),nullable=False,unique=True),sa.Column("expires_at",sa.DateTime(),nullable=False),sa.Column("confirmed_at",sa.DateTime()),sa.Column("result_json",sa.Text()),sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_index("ix_agent_confirmations_session_id","agent_confirmations",["session_id"]);op.create_index("ix_agent_confirmations_user_id","agent_confirmations",["user_id"])
    op.create_table("agent_runs",sa.Column("id",sa.String(36),primary_key=True),sa.Column("session_id",sa.String(36),sa.ForeignKey("agent_sessions.id"),nullable=False),sa.Column("request_id",sa.String(64),nullable=False),sa.Column("intent",sa.String(64)),sa.Column("status",sa.String(32),nullable=False),sa.Column("risk_level",sa.String(16),nullable=False),sa.Column("tool_name",sa.String(64)),sa.Column("summary_json",sa.Text()),sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_index("ix_agent_runs_session_id","agent_runs",["session_id"])
    op.create_table("agent_memories",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("memory_key",sa.String(80),nullable=False),sa.Column("value",sa.String(500),nullable=False),sa.Column("consented_at",sa.DateTime(),nullable=False),sa.Column("expires_at",sa.DateTime()),sa.Column("created_at",sa.DateTime(),nullable=False),sa.UniqueConstraint("user_id","memory_key"))
    op.create_table("agent_staff_reviews",sa.Column("id",sa.String(36),primary_key=True),sa.Column("session_id",sa.String(36),sa.ForeignKey("agent_sessions.id"),nullable=False),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("reason",sa.Text(),nullable=False),sa.Column("risk_level",sa.String(16),nullable=False),sa.Column("status",sa.String(24),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False))

def downgrade():
    op.drop_table("agent_staff_reviews");op.drop_table("agent_memories");op.drop_table("agent_runs");op.drop_table("agent_confirmations");op.drop_table("agent_messages");op.drop_table("agent_sessions")
