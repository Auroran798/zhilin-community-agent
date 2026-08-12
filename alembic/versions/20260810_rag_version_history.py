"""Preserve searchable chunks for every controlled knowledge version."""
from alembic import op
import sqlalchemy as sa

revision="20260810_rag_version_history"
down_revision="20260809_reliability_outbox"
branch_labels=None
depends_on=None


def upgrade():
    bind=op.get_bind()
    inspector=sa.inspect(bind)
    section_columns={column["name"] for column in inspector.get_columns("knowledge_sections")}
    section_indexes={index["name"] for index in inspector.get_indexes("knowledge_sections")}
    if "document_version" not in section_columns:
        with op.batch_alter_table("knowledge_sections") as batch:
            batch.add_column(sa.Column("document_version",sa.String(64),nullable=False,server_default="1.0"))
    if "ix_knowledge_sections_document_version" not in section_indexes:
        op.create_index("ix_knowledge_sections_document_version","knowledge_sections",["document_version"])

    chunk_columns={column["name"] for column in inspector.get_columns("knowledge_chunks")}
    if "document_version" not in chunk_columns:
        with op.batch_alter_table("knowledge_chunks") as batch:
            batch.add_column(sa.Column("document_version",sa.String(64),nullable=False,server_default="1.0"))
    op.execute("UPDATE knowledge_sections SET document_version = COALESCE((SELECT version FROM knowledge_documents WHERE knowledge_documents.id = knowledge_sections.document_id), '1.0')")
    op.execute("UPDATE knowledge_chunks SET document_version = COALESCE((SELECT version FROM knowledge_documents WHERE knowledge_documents.id = knowledge_chunks.document_id), '1.0')")

    inspector=sa.inspect(bind)
    unique_constraints=inspector.get_unique_constraints("knowledge_chunks")
    legacy=next((item for item in unique_constraints if item["column_names"]==["document_id","chunk_index"]),None)
    current=next((item for item in unique_constraints if item["column_names"]==["document_id","document_version","chunk_index"]),None)
    if legacy:
        if legacy.get("name"):
            with op.batch_alter_table("knowledge_chunks") as batch:
                batch.drop_constraint(legacy["name"],type_="unique")
        else:
            # Old SQLite demo databases were initially created by metadata and
            # therefore contain an unnamed UNIQUE(document_id, chunk_index).
            convention={"uq":"uq_%(table_name)s_%(column_0_name)s_%(column_1_name)s"}
            with op.batch_alter_table("knowledge_chunks",naming_convention=convention) as batch:
                batch.drop_constraint("uq_knowledge_chunks_document_id_chunk_index",type_="unique")
    if not current:
        with op.batch_alter_table("knowledge_chunks") as batch:
            batch.create_unique_constraint("uq_knowledge_chunk_document_version_index",["document_id","document_version","chunk_index"])
    chunk_indexes={index["name"] for index in sa.inspect(bind).get_indexes("knowledge_chunks")}
    if "ix_knowledge_chunks_document_version" not in chunk_indexes:
        op.create_index("ix_knowledge_chunks_document_version","knowledge_chunks",["document_version"])


def downgrade():
    # The old schema can represent only one index version per document.
    op.execute("DELETE FROM knowledge_chunks WHERE document_version != (SELECT version FROM knowledge_documents WHERE knowledge_documents.id = knowledge_chunks.document_id)")
    op.execute("DELETE FROM knowledge_sections WHERE document_version != (SELECT version FROM knowledge_documents WHERE knowledge_documents.id = knowledge_sections.document_id)")
    with op.batch_alter_table("knowledge_chunks") as batch:
        batch.drop_index("ix_knowledge_chunks_document_version")
        batch.drop_constraint("uq_knowledge_chunk_document_version_index",type_="unique")
        batch.create_unique_constraint("uq_knowledge_chunk_document_index",["document_id","chunk_index"])
        batch.drop_column("document_version")
    with op.batch_alter_table("knowledge_sections") as batch:
        batch.drop_index("ix_knowledge_sections_document_version")
        batch.drop_column("document_version")
