"""Stage 2 versions, jobs, feedback, and retrieval audit fields."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision="20260801_stage2_completion"
down_revision="20260801_stage2_sources"

def upgrade():
    inspector = inspect(op.get_bind())
    if inspector.has_table("knowledge_document_versions"):
        return
    op.create_table("knowledge_document_versions",sa.Column("id",sa.String(36),primary_key=True),sa.Column("document_id",sa.String(36),sa.ForeignKey("knowledge_documents.id"),nullable=False),sa.Column("version",sa.String(64),nullable=False),sa.Column("file_hash",sa.String(64),nullable=False),sa.Column("content_hash",sa.String(64)),sa.Column("storage_path",sa.String(500),nullable=False),sa.Column("effective_date",sa.DateTime()),sa.Column("expiry_date",sa.DateTime()),sa.Column("change_summary",sa.Text()),sa.Column("created_by",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False),sa.UniqueConstraint("document_id","version"))
    op.create_table("knowledge_ingestion_jobs",sa.Column("id",sa.String(36),primary_key=True),sa.Column("job_no",sa.String(48),unique=True,nullable=False),sa.Column("document_id",sa.String(36),sa.ForeignKey("knowledge_documents.id"),nullable=False),sa.Column("status",sa.String(32),nullable=False),sa.Column("current_step",sa.String(64),nullable=False),sa.Column("total_chunks",sa.Integer(),nullable=False),sa.Column("processed_chunks",sa.Integer(),nullable=False),sa.Column("error_code",sa.String(64)),sa.Column("error_message",sa.Text()),sa.Column("started_at",sa.DateTime()),sa.Column("finished_at",sa.DateTime()),sa.Column("created_by",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("created_at",sa.DateTime(),nullable=False))
    op.create_table("rag_feedback",sa.Column("id",sa.String(36),primary_key=True),sa.Column("rag_query_log_id",sa.String(36),sa.ForeignKey("rag_query_logs.id"),nullable=False),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("helpful",sa.Boolean(),nullable=False),sa.Column("feedback_type",sa.String(64)),sa.Column("comment",sa.Text()),sa.Column("created_at",sa.DateTime(),nullable=False))
    with op.batch_alter_table("knowledge_chunks") as b: b.add_column(sa.Column("is_suspicious",sa.Boolean(),server_default=sa.false()))
    with op.batch_alter_table("rag_query_logs") as b:
        for col in [sa.Column("normalized_query",sa.Text()),sa.Column("filters_json",sa.Text()),sa.Column("embedding_model",sa.String(100)),sa.Column("reranker_model",sa.String(100)),sa.Column("llm_model",sa.String(100)),sa.Column("answer_text_hash",sa.String(64)),sa.Column("error_code",sa.String(64))]: b.add_column(col)

def downgrade():
    with op.batch_alter_table("rag_query_logs") as b:
        for name in ["error_code","answer_text_hash","llm_model","reranker_model","embedding_model","filters_json","normalized_query"]: b.drop_column(name)
    with op.batch_alter_table("knowledge_chunks") as b: b.drop_column("is_suspicious")
    op.drop_table("rag_feedback");op.drop_table("knowledge_ingestion_jobs");op.drop_table("knowledge_document_versions")
