"""Stage 4 MCP governance and local observability."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision="20260803_stage4_mcp_harness"
down_revision="20260802_stage3_full"

def upgrade():
    inspector = inspect(op.get_bind())
    if inspector.has_table("execution_traces"):
        return
    op.create_table("execution_traces",sa.Column("id",sa.String(36),primary_key=True),sa.Column("trace_id",sa.String(64),nullable=False,unique=True),sa.Column("parent_trace_id",sa.String(64)),sa.Column("request_id",sa.String(64)),sa.Column("session_id",sa.String(36)),sa.Column("run_id",sa.String(36)),sa.Column("user_id",sa.String(36)),sa.Column("outcome",sa.String(32),nullable=False),sa.Column("error_code",sa.String(64)),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("finished_at",sa.DateTime()))
    op.create_table("execution_spans",sa.Column("id",sa.String(36),primary_key=True),sa.Column("trace_id",sa.String(64),nullable=False),sa.Column("span_id",sa.String(64),nullable=False,unique=True),sa.Column("parent_span_id",sa.String(64)),sa.Column("name",sa.String(96),nullable=False),sa.Column("kind",sa.String(32),nullable=False),sa.Column("status",sa.String(24),nullable=False),sa.Column("attributes_redacted",sa.Text()),sa.Column("error_code",sa.String(64)),sa.Column("started_at",sa.DateTime(),nullable=False),sa.Column("finished_at",sa.DateTime()),sa.Column("latency_ms",sa.Integer()))
    op.create_table("harness_executions",sa.Column("id",sa.String(36),primary_key=True),sa.Column("trace_id",sa.String(64),nullable=False),sa.Column("tool_name",sa.String(80),nullable=False),sa.Column("backend",sa.String(24),nullable=False),sa.Column("actor_id",sa.String(36)),sa.Column("operation_type",sa.String(16),nullable=False),sa.Column("idempotency_key",sa.String(128)),sa.Column("attempt",sa.Integer(),nullable=False),sa.Column("status",sa.String(24),nullable=False),sa.Column("error_code",sa.String(64)),sa.Column("input_redacted",sa.Text()),sa.Column("output_redacted",sa.Text()),sa.Column("latency_ms",sa.Integer()),sa.Column("created_at",sa.DateTime(),nullable=False))
    for table, cols in [("execution_traces",["trace_id","request_id","session_id","run_id","user_id","outcome","error_code"]),("execution_spans",["trace_id","span_id","parent_span_id","name","kind","status"]),("harness_executions",["trace_id","tool_name","backend","actor_id","operation_type","idempotency_key","status"])]:
        for col in cols: op.create_index(f"ix_{table}_{col}",table,[col])

def downgrade():
    op.drop_table("harness_executions");op.drop_table("execution_spans");op.drop_table("execution_traces")
