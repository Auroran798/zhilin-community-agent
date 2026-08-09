"""Scoped idempotency and durable integration outbox."""
from alembic import op
import sqlalchemy as sa

revision="20260809_reliability_outbox"
down_revision="20260808_stage7_business_closure"
branch_labels=None
depends_on=None


def upgrade():
    with op.batch_alter_table("agent_confirmations") as batch:
        batch.add_column(sa.Column("payload_hash",sa.String(64)))
    op.create_table("idempotency_records",
        sa.Column("id",sa.String(36),primary_key=True),
        sa.Column("actor_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("operation",sa.String(80),nullable=False),
        sa.Column("key_hash",sa.String(64),nullable=False),
        sa.Column("request_hash",sa.String(64),nullable=False),
        sa.Column("status",sa.String(16),nullable=False,server_default="in_progress"),
        sa.Column("resource_type",sa.String(40)),sa.Column("resource_id",sa.String(36)),
        sa.Column("response_json",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
        sa.Column("completed_at",sa.DateTime(timezone=True)),
        sa.UniqueConstraint("actor_id","operation","key_hash",name="uq_idempotency_actor_operation_key"))
    for column in ("actor_id","operation","status","resource_id"):op.create_index(f"ix_idempotency_records_{column}","idempotency_records",[column])
    op.create_table("outbox_events",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("event_type",sa.String(80),nullable=False),
        sa.Column("aggregate_type",sa.String(40),nullable=False),sa.Column("aggregate_id",sa.String(36),nullable=False),
        sa.Column("actor_id",sa.String(36),sa.ForeignKey("users.id")),sa.Column("payload_json",sa.Text(),nullable=False),
        sa.Column("idempotency_key",sa.String(200),nullable=False,unique=True),sa.Column("status",sa.String(20),nullable=False,server_default="pending"),
        sa.Column("attempts",sa.Integer(),nullable=False,server_default="0"),sa.Column("next_attempt_at",sa.DateTime(timezone=True)),
        sa.Column("last_error",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("processed_at",sa.DateTime(timezone=True)))
    for column in ("event_type","aggregate_type","aggregate_id","actor_id","status","next_attempt_at","created_at"):op.create_index(f"ix_outbox_events_{column}","outbox_events",[column])


def downgrade():
    op.drop_table("outbox_events")
    op.drop_table("idempotency_records")
    with op.batch_alter_table("agent_confirmations") as batch:
        batch.drop_column("payload_hash")
