"""Add explicit product modes and governed data classes.

Revision ID: 20260810_domestic_beijing_modes
"""
from alembic import op
import sqlalchemy as sa

revision="20260810_domestic_beijing_modes"
down_revision="20260810_rag_source_governance"
branch_labels=None
depends_on=None


def _add(table, columns):
    existing={item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
    with op.batch_alter_table(table) as batch:
        for column in columns:
            if column.name not in existing:
                batch.add_column(column)


def _index(table, column):
    name=f"ix_{table}_{column}"
    if name not in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}:
        op.create_index(name,table,[column])


def upgrade():
    for table in ("knowledge_documents","knowledge_sources"):
        _add(table,[sa.Column("data_class",sa.String(32),nullable=False,server_default="KB_POLICY")])
        _index(table,"data_class")
    _add("rag_query_logs",[
        sa.Column("product_mode",sa.String(32),nullable=False,server_default="domestic_beijing"),
        sa.Column("resolved_jurisdiction",sa.String(120),nullable=True),
    ])
    _index("rag_query_logs","product_mode");_index("rag_query_logs","resolved_jurisdiction")
    _add("agent_sessions",[
        sa.Column("product_mode",sa.String(32),nullable=False,server_default="domestic_beijing"),
        sa.Column("jurisdiction",sa.String(120),nullable=True),
    ])
    _index("agent_sessions","product_mode");_index("agent_sessions","jurisdiction")


def downgrade():
    for table,columns in (
        ("agent_sessions",("jurisdiction","product_mode")),
        ("rag_query_logs",("resolved_jurisdiction","product_mode")),
        ("knowledge_sources",("data_class",)),
        ("knowledge_documents",("data_class",)),
    ):
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.drop_index(f"ix_{table}_{column}")
                batch.drop_column(column)
