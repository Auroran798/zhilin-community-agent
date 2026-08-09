"""Stage 2 source registry and announcement traceability."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision="20260801_stage2_sources"
down_revision="20260801_stage2_knowledge"

def upgrade():
    # The initial revision creates the current ORM metadata for a brand-new
    # database.  In that case this historical revision is already represented
    # and must be a no-op instead of recreating the table/columns.
    inspector = inspect(op.get_bind())
    if inspector.has_table("knowledge_sources"):
        return
    op.create_table("knowledge_sources",
        sa.Column("id",sa.String(36),primary_key=True), sa.Column("source_no",sa.String(48),nullable=False,unique=True),
        sa.Column("title",sa.String(255),nullable=False),sa.Column("source_type",sa.String(64),nullable=False),sa.Column("source_url",sa.String(500),nullable=False,unique=True),
        sa.Column("publisher",sa.String(255)),sa.Column("publication_date",sa.DateTime()),sa.Column("acquired_at",sa.DateTime(),nullable=False),sa.Column("version",sa.String(64)),sa.Column("effective_date",sa.DateTime()),sa.Column("expiry_date",sa.DateTime()),sa.Column("authority_status",sa.String(32)),sa.Column("jurisdiction",sa.String(120)),sa.Column("file_type",sa.String(20)),sa.Column("file_hash",sa.String(64)),sa.Column("license_note",sa.String(500)),sa.Column("actually_downloaded",sa.Boolean(),server_default=sa.false()),sa.Column("manually_verified",sa.Boolean(),server_default=sa.false()),sa.Column("notes",sa.Text()),sa.Column("created_at",sa.DateTime(),nullable=False))
    with op.batch_alter_table("knowledge_documents") as b:
        b.add_column(sa.Column("source_id",sa.String(36),nullable=True)); b.add_column(sa.Column("source_business_type",sa.String(64),nullable=True)); b.add_column(sa.Column("source_business_id",sa.String(36),nullable=True)); b.add_column(sa.Column("jurisdiction",sa.String(120),nullable=True)); b.add_column(sa.Column("publication_date",sa.DateTime(),nullable=True)); b.add_column(sa.Column("acquired_at",sa.DateTime(),nullable=True)); b.add_column(sa.Column("authority_status",sa.String(32),nullable=True)); b.add_column(sa.Column("license_note",sa.String(500),nullable=True)); b.add_column(sa.Column("is_authoritative",sa.Boolean(),server_default=sa.false())); b.add_column(sa.Column("is_synthetic",sa.Boolean(),server_default=sa.false())); b.create_foreign_key("fk_knowledge_documents_source","knowledge_sources",["source_id"],["id"])
    op.create_index("ix_knowledge_documents_source_business", "knowledge_documents", ["source_business_type","source_business_id"])

def downgrade():
    op.drop_index("ix_knowledge_documents_source_business",table_name="knowledge_documents")
    with op.batch_alter_table("knowledge_documents") as b:
        b.drop_constraint("fk_knowledge_documents_source",type_="foreignkey")
        for col in ["is_synthetic","is_authoritative","license_note","authority_status","acquired_at","publication_date","jurisdiction","source_business_id","source_business_type","source_id"]: b.drop_column(col)
    op.drop_table("knowledge_sources")
