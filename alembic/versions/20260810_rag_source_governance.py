"""Add governed multilingual source metadata required by the final RAG design."""
from alembic import op
import sqlalchemy as sa

revision="20260810_rag_source_governance"
down_revision="20260810_rag_version_history"
branch_labels=None
depends_on=None


def common_columns():
    return (
        sa.Column("country", sa.String(32), nullable=True),
        sa.Column("language", sa.String(16), nullable=False, server_default="zh-CN"),
        sa.Column("answerable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("authority_level", sa.String(32), nullable=False, server_default="community"),
        sa.Column("license_url", sa.String(500), nullable=True),
        sa.Column("contains_personal_data", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("minimization_rule", sa.String(500), nullable=True),
        sa.Column("parser_version", sa.String(64), nullable=False, server_default="structured-v1"),
        sa.Column("review_status", sa.String(32), nullable=False, server_default="approved"),
        sa.Column("translation_provider", sa.String(100), nullable=True),
        sa.Column("translation_model", sa.String(100), nullable=True),
        sa.Column("translation_version", sa.String(64), nullable=True),
    )


def upgrade():
    for table in ("knowledge_documents", "knowledge_sources"):
        existing={column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}
        with op.batch_alter_table(table) as batch:
            for column in common_columns():
                if column.name not in existing:
                    batch.add_column(column)
        indexes={index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}
        for column in ("country", "language", "answerable", "authority_level", "review_status"):
            name=f"ix_{table}_{column}"
            if name not in indexes:
                op.create_index(name, table, [column])


def downgrade():
    for table in ("knowledge_sources", "knowledge_documents"):
        with op.batch_alter_table(table) as batch:
            for column in ("country", "language", "answerable", "authority_level", "review_status"):
                batch.drop_index(f"ix_{table}_{column}")
            for column in reversed(common_columns()):
                batch.drop_column(column.name)
