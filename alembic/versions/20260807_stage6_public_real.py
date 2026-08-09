"""stage6 public real data schema

Revision ID: 20260807_stage6_public_real
Revises: 20260803_stage4_mcp_harness
"""
from alembic import op
import sqlalchemy as sa

revision = "20260807_stage6_public_real"
down_revision = "20260803_stage4_mcp_harness"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("public_datasets"):
        op.create_table("public_datasets",sa.Column("dataset_id",sa.String(64),primary_key=True),sa.Column("dataset_name",sa.String(255),nullable=False),sa.Column("country",sa.String(32),nullable=False),sa.Column("city",sa.String(100),nullable=False),sa.Column("publisher",sa.String(255),nullable=False),sa.Column("source_url",sa.String(500),nullable=False),sa.Column("api_url",sa.String(500),nullable=False),sa.Column("license",sa.Text(),nullable=False),sa.Column("license_url",sa.String(500),nullable=False),sa.Column("manifest_path",sa.String(500),nullable=False),sa.Column("row_count",sa.Integer(),nullable=False,server_default="0"),sa.Column("imported_at",sa.DateTime()),sa.Column("created_at",sa.DateTime(),nullable=False))
        for column in ("dataset_name","country","city"): op.create_index(f"ix_public_datasets_{column}","public_datasets",[column])
    if not inspector.has_table("public_cases"):
        op.create_table("public_cases",sa.Column("id",sa.String(36),primary_key=True),sa.Column("source_type",sa.String(32),nullable=False),sa.Column("source_country",sa.String(32),nullable=False),sa.Column("source_dataset",sa.String(255),nullable=False),sa.Column("source_dataset_id",sa.String(64),sa.ForeignKey("public_datasets.dataset_id"),nullable=False),sa.Column("source_record_id",sa.String(128),nullable=False),sa.Column("source_url",sa.String(500),nullable=False),sa.Column("source_license",sa.Text(),nullable=False),sa.Column("source_retrieved_at",sa.DateTime(),nullable=False),sa.Column("original_language",sa.String(16),nullable=False),sa.Column("translation_status",sa.String(32),nullable=False),sa.Column("normalization_version",sa.String(32),nullable=False),sa.Column("mapping_version",sa.String(32),nullable=False),sa.Column("record_kind",sa.String(40),nullable=False),sa.Column("external_category",sa.String(128)),sa.Column("external_subcategory",sa.String(255)),sa.Column("source_status",sa.String(128)),sa.Column("normalized_status",sa.String(32)),sa.Column("original_text",sa.Text()),sa.Column("sanitized_text",sa.Text()),sa.Column("normalized_category",sa.String(32),nullable=False),sa.Column("normalized_subcategory",sa.String(64)),sa.Column("risk_level",sa.String(16),nullable=False),sa.Column("mapping_method",sa.String(64),nullable=False),sa.Column("mapping_confidence",sa.Numeric(4,3),nullable=False),sa.Column("occurred_at",sa.DateTime()),sa.Column("resolved_at",sa.DateTime()),sa.Column("location_city",sa.String(100)),sa.Column("location_district",sa.String(100)),sa.Column("location_zip_prefix",sa.String(8)),sa.Column("source_payload_json",sa.Text()),sa.Column("imported_at",sa.DateTime(),nullable=False),sa.UniqueConstraint("source_dataset_id","source_record_id",name="uq_public_case_source_record"))
        for column in ("source_type","source_country","source_dataset","source_dataset_id","source_record_id","record_kind","external_category","source_status","normalized_status","normalized_category","risk_level","occurred_at","resolved_at","location_district","location_zip_prefix"): op.create_index(f"ix_public_cases_{column}","public_cases",[column])
        op.create_index("ix_public_cases_dataset_kind_occurred","public_cases",["source_dataset_id","record_kind","occurred_at"])


def downgrade():
    op.drop_table("public_cases")
    op.drop_table("public_datasets")
