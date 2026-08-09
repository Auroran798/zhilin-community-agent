import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base
from .time import utc_now

def uid(): return str(uuid.uuid4())
def now(): return utc_now()

class User(Base):
    __tablename__="users"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    username: Mapped[str]=mapped_column(String(64),unique=True,index=True)
    password_hash: Mapped[str]=mapped_column(String(255))
    display_name: Mapped[str]=mapped_column(String(80))
    phone_masked: Mapped[str]=mapped_column(String(32),default="138****0000")
    role: Mapped[str]=mapped_column(String(32),index=True)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime,default=now,onupdate=now)

class Property(Base):
    __tablename__="properties"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    community_name: Mapped[str]=mapped_column(String(100),index=True)
    building_no: Mapped[str]=mapped_column(String(12),index=True)
    unit_no: Mapped[str]=mapped_column(String(12))
    room_no: Mapped[str]=mapped_column(String(12))
    floor: Mapped[int]=mapped_column(Integer)
    property_type: Mapped[str]=mapped_column(String(32),default="residential")
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    __table_args__=(UniqueConstraint("community_name","building_no","unit_no","room_no"),)

class Binding(Base):
    __tablename__="user_property_bindings"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    property_id: Mapped[str]=mapped_column(ForeignKey("properties.id"),index=True)
    binding_type: Mapped[str]=mapped_column(String(32),default="owner")
    is_primary: Mapped[bool]=mapped_column(Boolean,default=True)
    verified_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    __table_args__=(UniqueConstraint("user_id","property_id"),)

class WorkOrder(Base):
    __tablename__="work_orders"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    work_order_no: Mapped[str]=mapped_column(String(32),unique=True,index=True)
    requester_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    property_id: Mapped[str]=mapped_column(ForeignKey("properties.id"),index=True)
    original_description: Mapped[str]=mapped_column(Text)
    summary: Mapped[str]=mapped_column(Text)
    category: Mapped[str]=mapped_column(String(32),index=True)
    subcategory: Mapped[str|None]=mapped_column(String(32),nullable=True)
    location_description: Mapped[str]=mapped_column(String(200))
    equipment_name: Mapped[str|None]=mapped_column(String(100),nullable=True)
    equipment_id: Mapped[str|None]=mapped_column(ForeignKey("equipment.id"),nullable=True,index=True)
    fault_description: Mapped[str]=mapped_column(Text)
    impact_scope: Mapped[str]=mapped_column(String(32),default="single")
    risk_level: Mapped[str]=mapped_column(String(16),default="low",index=True)
    priority: Mapped[str]=mapped_column(String(8),default="P3",index=True)
    status: Mapped[str]=mapped_column(String(16),default="待受理",index=True)
    assignee_id: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    contact_phone_masked: Mapped[str]=mapped_column(String(32))
    request_channel: Mapped[str]=mapped_column(String(32),default="web")
    requires_manual_escalation: Mapped[bool]=mapped_column(Boolean,default=False)
    manual_escalation_reason: Mapped[str|None]=mapped_column(Text,nullable=True)
    resolution: Mapped[str|None]=mapped_column(Text,nullable=True)
    source_type: Mapped[str]=mapped_column(String(32),default="synthetic")
    idempotency_key: Mapped[str|None]=mapped_column(String(100),unique=True,nullable=True)
    sla_policy_id: Mapped[str|None]=mapped_column(ForeignKey("sla_policies.id"),nullable=True,index=True)
    response_deadline: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True,index=True)
    processing_deadline: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True,index=True)
    first_response_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    sla_response_status: Mapped[str]=mapped_column(String(16),default="normal",index=True)
    sla_processing_status: Mapped[str]=mapped_column(String(16),default="normal",index=True)
    overdue_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now,index=True)
    accepted_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    assigned_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    started_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    completed_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    closed_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    updated_at: Mapped[datetime]=mapped_column(DateTime,default=now,onupdate=now)

class WorkOrderEvent(Base):
    __tablename__="work_order_events"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    work_order_id: Mapped[str]=mapped_column(ForeignKey("work_orders.id"),index=True)
    event_type: Mapped[str]=mapped_column(String(32))
    from_status: Mapped[str|None]=mapped_column(String(16),nullable=True)
    to_status: Mapped[str|None]=mapped_column(String(16),nullable=True)
    operator_id: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    note: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class WorkOrderRating(Base):
    __tablename__="work_order_ratings"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    work_order_id: Mapped[str]=mapped_column(ForeignKey("work_orders.id"),unique=True)
    resident_id: Mapped[str]=mapped_column(ForeignKey("users.id"))
    score: Mapped[int]=mapped_column(Integer)
    comment: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class Announcement(Base):
    __tablename__="announcements"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    title: Mapped[str]=mapped_column(String(160))
    announcement_type: Mapped[str]=mapped_column(String(32))
    content: Mapped[str]=mapped_column(Text)
    affected_scope: Mapped[str]=mapped_column(String(160))
    target_type: Mapped[str]=mapped_column(String(16),default="all",index=True)
    target_building_no: Mapped[str|None]=mapped_column(String(12),nullable=True,index=True)
    summary: Mapped[str|None]=mapped_column(Text,nullable=True)
    suggested_publish_time: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    scheduled_publish_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True,index=True)
    start_time: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    end_time: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    contact_information: Mapped[str]=mapped_column(String(160))
    publisher_unit: Mapped[str]=mapped_column(String(100))
    status: Mapped[str]=mapped_column(String(20),default="draft",index=True)
    created_by: Mapped[str]=mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    published_by: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    reviewed_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    published_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    updated_at: Mapped[datetime]=mapped_column(DateTime,default=now,onupdate=now)

class Bill(Base):
    __tablename__="bills"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    bill_no: Mapped[str]=mapped_column(String(32),unique=True,index=True)
    property_id: Mapped[str]=mapped_column(ForeignKey("properties.id"),index=True)
    billing_period: Mapped[str]=mapped_column(String(7),index=True)
    bill_type: Mapped[str]=mapped_column(String(32))
    amount: Mapped[Decimal]=mapped_column(Numeric(12,2))
    paid_amount: Mapped[Decimal]=mapped_column(Numeric(12,2),default=Decimal("0.00"))
    status: Mapped[str]=mapped_column(String(16))
    due_date: Mapped[datetime]=mapped_column(DateTime)
    source_type: Mapped[str]=mapped_column(String(32),default="synthetic")
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class BillItem(Base):
    __tablename__="bill_items"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    bill_id: Mapped[str]=mapped_column(ForeignKey("bills.id"),index=True)
    item_type: Mapped[str]=mapped_column(String(32),index=True)
    item_name: Mapped[str]=mapped_column(String(120))
    amount: Mapped[Decimal]=mapped_column(Numeric(12,2))
    quantity: Mapped[Decimal|None]=mapped_column(Numeric(12,2),nullable=True)
    unit_price: Mapped[Decimal|None]=mapped_column(Numeric(12,2),nullable=True)
    description: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

class PaymentRecord(Base):
    __tablename__="payment_records"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    bill_id: Mapped[str]=mapped_column(ForeignKey("bills.id"),index=True)
    payment_no: Mapped[str]=mapped_column(String(32),unique=True)
    amount: Mapped[Decimal]=mapped_column(Numeric(12,2))
    paid_at: Mapped[datetime]=mapped_column(DateTime)
    payment_channel: Mapped[str]=mapped_column(String(32),default="mock")
    status: Mapped[str]=mapped_column(String(16),default="paid")
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class BillReviewRequest(Base):
    __tablename__="bill_review_requests"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    request_no: Mapped[str]=mapped_column(String(32),unique=True)
    bill_id: Mapped[str]=mapped_column(ForeignKey("bills.id"),index=True)
    resident_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    reason: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(16),default="pending")
    handler_id: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    result: Mapped[str|None]=mapped_column(Text,nullable=True)
    idempotency_key: Mapped[str|None]=mapped_column(String(100),unique=True,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    handled_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)

class InspectionTask(Base):
    __tablename__="inspection_tasks"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    task_no: Mapped[str]=mapped_column(String(32),unique=True)
    area_type: Mapped[str]=mapped_column(String(32))
    location_description: Mapped[str]=mapped_column(String(200))
    scheduled_at: Mapped[datetime]=mapped_column(DateTime)
    assignee_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    status: Mapped[str]=mapped_column(String(16),default="assigned")
    created_by: Mapped[str]=mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    completed_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    plan_id: Mapped[str|None]=mapped_column(ForeignKey("inspection_plans.id"),nullable=True,index=True)
    period_key: Mapped[str|None]=mapped_column(String(16),nullable=True)
    equipment_id: Mapped[str|None]=mapped_column(ForeignKey("equipment.id"),nullable=True,index=True)
    __table_args__=(UniqueConstraint("plan_id","period_key",name="uq_inspection_task_plan_period"),)

class InspectionRecord(Base):
    __tablename__="inspection_records"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    inspection_task_id: Mapped[str]=mapped_column(ForeignKey("inspection_tasks.id"),index=True)
    inspector_id: Mapped[str]=mapped_column(ForeignKey("users.id"))
    description: Mapped[str]=mapped_column(Text)
    abnormal: Mapped[bool]=mapped_column(Boolean)
    risk_level: Mapped[str]=mapped_column(String(16))
    attachment_path: Mapped[str|None]=mapped_column(String(255),nullable=True)
    submitted_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    idempotency_key: Mapped[str|None]=mapped_column(String(100),unique=True,nullable=True)

class RectificationOrder(Base):
    __tablename__="rectification_orders"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    rectification_no: Mapped[str]=mapped_column(String(32),unique=True)
    inspection_record_id: Mapped[str]=mapped_column(ForeignKey("inspection_records.id"),unique=True)
    description: Mapped[str]=mapped_column(Text)
    risk_level: Mapped[str]=mapped_column(String(16))
    status: Mapped[str]=mapped_column(String(16),default="待整改")
    assignee_id: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    deadline: Mapped[datetime]=mapped_column(DateTime)
    resolution: Mapped[str|None]=mapped_column(Text,nullable=True)
    review_result: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    completed_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    reviewed_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    equipment_id: Mapped[str|None]=mapped_column(ForeignKey("equipment.id"),nullable=True,index=True)

class AuditLog(Base):
    __tablename__="audit_logs"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    actor_id: Mapped[str|None]=mapped_column(String(36),nullable=True,index=True)
    actor_role: Mapped[str|None]=mapped_column(String(32),nullable=True)
    action: Mapped[str]=mapped_column(String(80),index=True)
    resource_type: Mapped[str]=mapped_column(String(40))
    resource_id: Mapped[str|None]=mapped_column(String(36),nullable=True)
    request_method: Mapped[str|None]=mapped_column(String(12),nullable=True)
    request_path: Mapped[str|None]=mapped_column(String(255),nullable=True)
    request_id: Mapped[str]=mapped_column(String(64),index=True)
    result: Mapped[str]=mapped_column(String(16))
    failure_reason: Mapped[str|None]=mapped_column(String(255),nullable=True)
    metadata_json: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class IdempotencyRecord(Base):
    __tablename__="idempotency_records"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    actor_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    operation: Mapped[str]=mapped_column(String(80),index=True)
    key_hash: Mapped[str]=mapped_column(String(64))
    request_hash: Mapped[str]=mapped_column(String(64))
    status: Mapped[str]=mapped_column(String(16),default="in_progress",index=True)
    resource_type: Mapped[str|None]=mapped_column(String(40),nullable=True)
    resource_id: Mapped[str|None]=mapped_column(String(36),nullable=True,index=True)
    response_json: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    __table_args__=(UniqueConstraint("actor_id","operation","key_hash",name="uq_idempotency_actor_operation_key"),)

class OutboxEvent(Base):
    __tablename__="outbox_events"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    event_type: Mapped[str]=mapped_column(String(80),index=True)
    aggregate_type: Mapped[str]=mapped_column(String(40),index=True)
    aggregate_id: Mapped[str]=mapped_column(String(36),index=True)
    actor_id: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    payload_json: Mapped[str]=mapped_column(Text)
    idempotency_key: Mapped[str]=mapped_column(String(200),unique=True)
    status: Mapped[str]=mapped_column(String(20),default="pending",index=True)
    attempts: Mapped[int]=mapped_column(Integer,default=0)
    next_attempt_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True,index=True)
    last_error: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
    processed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class KnowledgeDocument(Base):
    __tablename__="knowledge_documents"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    document_no: Mapped[str]=mapped_column(String(40),unique=True,index=True)
    title: Mapped[str]=mapped_column(String(255),index=True)
    document_type: Mapped[str]=mapped_column(String(64),index=True)
    source_type: Mapped[str]=mapped_column(String(64))
    source_id: Mapped[str|None]=mapped_column(ForeignKey("knowledge_sources.id"),nullable=True)
    source_business_type: Mapped[str|None]=mapped_column(String(64),nullable=True)
    source_business_id: Mapped[str|None]=mapped_column(String(36),nullable=True)
    source_url: Mapped[str|None]=mapped_column(String(500),nullable=True)
    publisher: Mapped[str|None]=mapped_column(String(255),nullable=True)
    jurisdiction: Mapped[str|None]=mapped_column(String(120),nullable=True)
    publication_date: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    acquired_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    authority_status: Mapped[str|None]=mapped_column(String(32),nullable=True)
    license_note: Mapped[str|None]=mapped_column(String(500),nullable=True)
    is_authoritative: Mapped[bool|None]=mapped_column(Boolean,default=False,nullable=True)
    is_synthetic: Mapped[bool|None]=mapped_column(Boolean,default=False,nullable=True)
    applicable_community: Mapped[str|None]=mapped_column(String(100),nullable=True,index=True)
    version: Mapped[str]=mapped_column(String(64),default="1.0")
    effective_date: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    expiry_date: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    status: Mapped[str]=mapped_column(String(32),default="uploaded",index=True)
    file_name: Mapped[str]=mapped_column(String(255))
    file_type: Mapped[str]=mapped_column(String(20))
    file_size: Mapped[int]=mapped_column(Integer)
    file_hash: Mapped[str]=mapped_column(String(64),unique=True,index=True)
    storage_path: Mapped[str]=mapped_column(String(500))
    content_hash: Mapped[str|None]=mapped_column(String(64),nullable=True,index=True)
    raw_text: Mapped[str|None]=mapped_column(Text,nullable=True)
    cleaned_text: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_by: Mapped[str]=mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime,default=now,onupdate=now)
    indexed_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    __table_args__=(Index("ix_knowledge_documents_source_business","source_business_type","source_business_id"),)

class KnowledgeSource(Base):
    __tablename__="knowledge_sources"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    source_no: Mapped[str]=mapped_column(String(48),unique=True)
    title: Mapped[str]=mapped_column(String(255))
    source_type: Mapped[str]=mapped_column(String(64))
    source_url: Mapped[str]=mapped_column(String(500),unique=True)
    publisher: Mapped[str|None]=mapped_column(String(255),nullable=True)
    publication_date: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    acquired_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    version: Mapped[str|None]=mapped_column(String(64),nullable=True)
    effective_date: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    expiry_date: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    authority_status: Mapped[str|None]=mapped_column(String(32),nullable=True)
    jurisdiction: Mapped[str|None]=mapped_column(String(120),nullable=True)
    file_type: Mapped[str|None]=mapped_column(String(20),nullable=True)
    file_hash: Mapped[str|None]=mapped_column(String(64),nullable=True)
    license_note: Mapped[str|None]=mapped_column(String(500),nullable=True)
    actually_downloaded: Mapped[bool|None]=mapped_column(Boolean,default=False,nullable=True)
    manually_verified: Mapped[bool|None]=mapped_column(Boolean,default=False,nullable=True)
    notes: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class KnowledgeSection(Base):
    __tablename__="knowledge_sections"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    document_id: Mapped[str]=mapped_column(ForeignKey("knowledge_documents.id"),index=True)
    section_no: Mapped[str]=mapped_column(String(64))
    heading: Mapped[str|None]=mapped_column(String(255),nullable=True)
    clause_number: Mapped[str|None]=mapped_column(String(64),nullable=True)
    page_start: Mapped[int|None]=mapped_column(Integer,nullable=True)
    page_end: Mapped[int|None]=mapped_column(Integer,nullable=True)
    order_index: Mapped[int]=mapped_column(Integer)
    text: Mapped[str]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class KnowledgeChunk(Base):
    __tablename__="knowledge_chunks"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    chunk_uid: Mapped[str]=mapped_column(String(128),unique=True,index=True)
    document_id: Mapped[str]=mapped_column(ForeignKey("knowledge_documents.id"),index=True)
    section_id: Mapped[str|None]=mapped_column(ForeignKey("knowledge_sections.id"),nullable=True)
    chunk_index: Mapped[int]=mapped_column(Integer)
    text: Mapped[str]=mapped_column(Text)
    token_count: Mapped[int]=mapped_column(Integer)
    heading_path: Mapped[str|None]=mapped_column(String(500),nullable=True)
    clause_number: Mapped[str|None]=mapped_column(String(64),nullable=True)
    vector_collection: Mapped[str|None]=mapped_column(String(100),nullable=True)
    vector_id: Mapped[str|None]=mapped_column(String(128),nullable=True)
    embedding_model: Mapped[str|None]=mapped_column(String(100),nullable=True)
    content_hash: Mapped[str]=mapped_column(String(64),index=True)
    metadata_json: Mapped[str|None]=mapped_column(Text,nullable=True)
    is_suspicious: Mapped[bool|None]=mapped_column(Boolean,default=False,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    __table_args__=(UniqueConstraint("document_id","chunk_index"),)

class RagQueryLog(Base):
    __tablename__="rag_query_logs"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    request_id: Mapped[str]=mapped_column(String(64),index=True)
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    user_role: Mapped[str]=mapped_column(String(32))
    community_id: Mapped[str|None]=mapped_column(String(100),nullable=True)
    query: Mapped[str]=mapped_column(Text)
    normalized_query: Mapped[str|None]=mapped_column(Text,nullable=True)
    retrieval_mode: Mapped[str]=mapped_column(String(32))
    top_k: Mapped[int]=mapped_column(Integer)
    filters_json: Mapped[str|None]=mapped_column(Text,nullable=True)
    embedding_model: Mapped[str|None]=mapped_column(String(100),nullable=True)
    reranker_model: Mapped[str|None]=mapped_column(String(100),nullable=True)
    llm_model: Mapped[str|None]=mapped_column(String(100),nullable=True)
    retrieved_chunk_ids: Mapped[str|None]=mapped_column(Text,nullable=True)
    answer_status: Mapped[str]=mapped_column(String(32))
    citation_count: Mapped[int]=mapped_column(Integer,default=0)
    answer_text_hash: Mapped[str|None]=mapped_column(String(64),nullable=True)
    error_code: Mapped[str|None]=mapped_column(String(64),nullable=True)
    latency_ms: Mapped[int]=mapped_column(Integer)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class KnowledgeDocumentVersion(Base):
    __tablename__="knowledge_document_versions"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    document_id: Mapped[str]=mapped_column(ForeignKey("knowledge_documents.id"))
    version: Mapped[str]=mapped_column(String(64))
    file_hash: Mapped[str]=mapped_column(String(64))
    content_hash: Mapped[str|None]=mapped_column(String(64),nullable=True)
    storage_path: Mapped[str]=mapped_column(String(500))
    effective_date: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    expiry_date: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    change_summary: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_by: Mapped[str]=mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    __table_args__=(UniqueConstraint("document_id","version"),)

class KnowledgeIngestionJob(Base):
    __tablename__="knowledge_ingestion_jobs"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    job_no: Mapped[str]=mapped_column(String(48),unique=True)
    document_id: Mapped[str]=mapped_column(ForeignKey("knowledge_documents.id"))
    status: Mapped[str]=mapped_column(String(32),default="queued")
    current_step: Mapped[str]=mapped_column(String(64),default="queued")
    total_chunks: Mapped[int]=mapped_column(Integer,default=0)
    processed_chunks: Mapped[int]=mapped_column(Integer,default=0)
    error_code: Mapped[str|None]=mapped_column(String(64),nullable=True)
    error_message: Mapped[str|None]=mapped_column(Text,nullable=True)
    started_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    finished_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    created_by: Mapped[str]=mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class RagFeedback(Base):
    __tablename__="rag_feedback"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    rag_query_log_id: Mapped[str]=mapped_column(ForeignKey("rag_query_logs.id"))
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id"))
    helpful: Mapped[bool]=mapped_column(Boolean)
    feedback_type: Mapped[str|None]=mapped_column(String(64),nullable=True)
    comment: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class AgentSession(Base):
    __tablename__="agent_sessions"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    session_no: Mapped[str|None]=mapped_column(String(48),default=lambda:f"AS-{uuid.uuid4().hex[:16].upper()}",nullable=True)
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    thread_id: Mapped[str|None]=mapped_column(String(64),default=uid,nullable=True)
    current_skill: Mapped[str|None]=mapped_column(String(64),nullable=True)
    current_intent: Mapped[str|None]=mapped_column(String(64),nullable=True)
    community_name: Mapped[str|None]=mapped_column(String(100),nullable=True)
    property_id: Mapped[str|None]=mapped_column(ForeignKey("properties.id"),nullable=True)
    status: Mapped[str]=mapped_column(String(24),default="active")
    follow_up_rounds: Mapped[int]=mapped_column(Integer,default=0)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime,default=now,onupdate=now)
    closed_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    __table_args__=(UniqueConstraint("session_no",name="uq_agent_sessions_session_no"),UniqueConstraint("thread_id",name="uq_agent_sessions_thread_id"))

class AgentMessage(Base):
    __tablename__="agent_messages"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    session_id: Mapped[str]=mapped_column(ForeignKey("agent_sessions.id"),index=True)
    role: Mapped[str]=mapped_column(String(16))
    content: Mapped[str]=mapped_column(Text)
    content_redacted: Mapped[str|None]=mapped_column(Text,nullable=True)
    message_type: Mapped[str]=mapped_column(String(32),default="chat")
    tool_call_id: Mapped[str|None]=mapped_column(String(36),nullable=True)
    metadata_json: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class AgentConfirmation(Base):
    __tablename__="agent_confirmations"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    session_id: Mapped[str]=mapped_column(ForeignKey("agent_sessions.id"),index=True)
    run_id: Mapped[str|None]=mapped_column(ForeignKey("agent_runs.id"),nullable=True)
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    action: Mapped[str]=mapped_column(String(64))
    action_type: Mapped[str|None]=mapped_column(String(64),nullable=True)
    preview_json: Mapped[str]=mapped_column(Text)
    payload_hash: Mapped[str|None]=mapped_column(String(64),nullable=True)
    status: Mapped[str]=mapped_column(String(24),default="pending")
    idempotency_key: Mapped[str]=mapped_column(String(100),unique=True)
    expires_at: Mapped[datetime]=mapped_column(DateTime)
    confirmed_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    cancelled_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    result_json: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class AgentRun(Base):
    __tablename__="agent_runs"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    run_no: Mapped[str|None]=mapped_column(String(48),default=lambda:f"AR-{uuid.uuid4().hex[:16].upper()}",nullable=True)
    session_id: Mapped[str]=mapped_column(ForeignKey("agent_sessions.id"),index=True)
    request_id: Mapped[str]=mapped_column(String(64))
    intent: Mapped[str|None]=mapped_column(String(64),nullable=True)
    intent_confidence: Mapped[float|None]=mapped_column(nullable=True)
    active_skill: Mapped[str|None]=mapped_column(String(64),nullable=True)
    status: Mapped[str]=mapped_column(String(32))
    risk_level: Mapped[str]=mapped_column(String(16),default="low")
    requires_manual_escalation: Mapped[bool]=mapped_column(Boolean,default=False)
    tool_name: Mapped[str|None]=mapped_column(String(64),nullable=True)
    llm_provider: Mapped[str|None]=mapped_column(String(64),nullable=True)
    llm_model: Mapped[str|None]=mapped_column(String(128),nullable=True)
    latency_ms: Mapped[int|None]=mapped_column(Integer,nullable=True)
    error_code: Mapped[str|None]=mapped_column(String(64),nullable=True)
    summary_json: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    finished_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    __table_args__=(UniqueConstraint("run_no",name="uq_agent_runs_run_no"),)

class AgentToolCall(Base):
    __tablename__="agent_tool_calls"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    run_id: Mapped[str]=mapped_column(ForeignKey("agent_runs.id"),index=True)
    tool_name: Mapped[str]=mapped_column(String(64),index=True)
    arguments_redacted: Mapped[str|None]=mapped_column(Text,nullable=True)
    idempotency_key: Mapped[str|None]=mapped_column(String(100),nullable=True)
    status: Mapped[str]=mapped_column(String(24),default="running")
    result_summary: Mapped[str|None]=mapped_column(Text,nullable=True)
    error_code: Mapped[str|None]=mapped_column(String(64),nullable=True)
    latency_ms: Mapped[int|None]=mapped_column(Integer,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    finished_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)

class AgentMemory(Base):
    __tablename__="agent_memories"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id"))
    memory_type: Mapped[str]=mapped_column(String(80),default="preference")
    memory_key: Mapped[str]=mapped_column(String(80))
    value: Mapped[str]=mapped_column(String(500))
    consented: Mapped[bool]=mapped_column(Boolean,default=True)
    consented_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    expires_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    updated_at: Mapped[datetime|None]=mapped_column(DateTime,default=now,onupdate=now,nullable=True)
    deleted_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    __table_args__=(UniqueConstraint("user_id","memory_key"),)

class AgentStaffReview(Base):
    __tablename__="agent_staff_reviews"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    review_no: Mapped[str|None]=mapped_column(String(48),default=lambda:f"AHR-{uuid.uuid4().hex[:16].upper()}",nullable=True)
    session_id: Mapped[str]=mapped_column(ForeignKey("agent_sessions.id"))
    run_id: Mapped[str|None]=mapped_column(ForeignKey("agent_runs.id"),nullable=True)
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id"))
    review_type: Mapped[str]=mapped_column(String(64),default="manual_service")
    reason: Mapped[str]=mapped_column(Text)
    summary: Mapped[str|None]=mapped_column(Text,nullable=True)
    risk_level: Mapped[str]=mapped_column(String(16))
    status: Mapped[str]=mapped_column(String(24),default="pending")
    assigned_to: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    result: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    handled_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    __table_args__=(UniqueConstraint("review_no",name="uq_agent_staff_reviews_review_no"),)

# Stage 4: local, queryable call-chain storage.  Payloads are redacted before persistence.
class ExecutionTrace(Base):
    __tablename__="execution_traces"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    trace_id: Mapped[str]=mapped_column(String(64),unique=True)
    parent_trace_id: Mapped[str|None]=mapped_column(String(64),nullable=True,index=True)
    request_id: Mapped[str|None]=mapped_column(String(64),nullable=True,index=True)
    session_id: Mapped[str|None]=mapped_column(String(36),nullable=True,index=True)
    run_id: Mapped[str|None]=mapped_column(String(36),nullable=True,index=True)
    user_id: Mapped[str|None]=mapped_column(String(36),nullable=True,index=True)
    outcome: Mapped[str]=mapped_column(String(32),default="running",index=True)
    error_code: Mapped[str|None]=mapped_column(String(64),nullable=True,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    finished_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    __table_args__=(Index("ix_execution_traces_trace_id","trace_id"),)

class ExecutionSpan(Base):
    __tablename__="execution_spans"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    trace_id: Mapped[str]=mapped_column(String(64),index=True)
    span_id: Mapped[str]=mapped_column(String(64),unique=True)
    parent_span_id: Mapped[str|None]=mapped_column(String(64),nullable=True,index=True)
    name: Mapped[str]=mapped_column(String(96),index=True)
    kind: Mapped[str]=mapped_column(String(32),index=True)
    status: Mapped[str]=mapped_column(String(24),default="running",index=True)
    attributes_redacted: Mapped[str|None]=mapped_column(Text,nullable=True)
    error_code: Mapped[str|None]=mapped_column(String(64),nullable=True)
    started_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    finished_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    latency_ms: Mapped[int|None]=mapped_column(Integer,nullable=True)
    __table_args__=(Index("ix_execution_spans_span_id","span_id"),)

class HarnessExecution(Base):
    __tablename__="harness_executions"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    trace_id: Mapped[str]=mapped_column(String(64),index=True)
    tool_name: Mapped[str]=mapped_column(String(80),index=True)
    backend: Mapped[str]=mapped_column(String(24),index=True)
    actor_id: Mapped[str|None]=mapped_column(String(36),nullable=True,index=True)
    operation_type: Mapped[str]=mapped_column(String(16),index=True)
    idempotency_key: Mapped[str|None]=mapped_column(String(128),nullable=True,index=True)
    attempt: Mapped[int]=mapped_column(Integer,default=1)
    status: Mapped[str]=mapped_column(String(24),index=True)
    error_code: Mapped[str|None]=mapped_column(String(64),nullable=True,index=True)
    input_redacted: Mapped[str|None]=mapped_column(Text,nullable=True)
    output_redacted: Mapped[str|None]=mapped_column(Text,nullable=True)
    latency_ms: Mapped[int|None]=mapped_column(Integer,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

# Stage 6: public regulatory records live outside tenant-facing synthetic data.
# They intentionally have no foreign key to residents, properties, bills or staff.
class PublicDataset(Base):
    __tablename__="public_datasets"
    dataset_id: Mapped[str]=mapped_column(String(64),primary_key=True)
    dataset_name: Mapped[str]=mapped_column(String(255),index=True)
    country: Mapped[str]=mapped_column(String(32),index=True)
    city: Mapped[str]=mapped_column(String(100),index=True)
    publisher: Mapped[str]=mapped_column(String(255))
    source_url: Mapped[str]=mapped_column(String(500))
    api_url: Mapped[str]=mapped_column(String(500))
    license: Mapped[str]=mapped_column(Text)
    license_url: Mapped[str]=mapped_column(String(500))
    manifest_path: Mapped[str]=mapped_column(String(500))
    row_count: Mapped[int]=mapped_column(Integer,default=0)
    imported_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=now)

class PublicCase(Base):
    __tablename__="public_cases"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    source_type: Mapped[str]=mapped_column(String(32),index=True)
    source_country: Mapped[str]=mapped_column(String(32),index=True)
    source_dataset: Mapped[str]=mapped_column(String(255),index=True)
    source_dataset_id: Mapped[str]=mapped_column(ForeignKey("public_datasets.dataset_id"),index=True)
    source_record_id: Mapped[str]=mapped_column(String(128),index=True)
    source_url: Mapped[str]=mapped_column(String(500))
    source_license: Mapped[str]=mapped_column(Text)
    source_retrieved_at: Mapped[datetime]=mapped_column(DateTime)
    original_language: Mapped[str]=mapped_column(String(16),default="en")
    translation_status: Mapped[str]=mapped_column(String(32),default="not_translated")
    normalization_version: Mapped[str]=mapped_column(String(32))
    mapping_version: Mapped[str]=mapped_column(String(32))
    record_kind: Mapped[str]=mapped_column(String(40),index=True)
    external_category: Mapped[str|None]=mapped_column(String(128),nullable=True,index=True)
    external_subcategory: Mapped[str|None]=mapped_column(String(255),nullable=True)
    source_status: Mapped[str|None]=mapped_column(String(128),nullable=True,index=True)
    normalized_status: Mapped[str|None]=mapped_column(String(32),nullable=True,index=True)
    original_text: Mapped[str|None]=mapped_column(Text,nullable=True)
    sanitized_text: Mapped[str|None]=mapped_column(Text,nullable=True)
    normalized_category: Mapped[str]=mapped_column(String(32),index=True)
    normalized_subcategory: Mapped[str|None]=mapped_column(String(64),nullable=True)
    risk_level: Mapped[str]=mapped_column(String(16),index=True)
    mapping_method: Mapped[str]=mapped_column(String(64))
    mapping_confidence: Mapped[float]=mapped_column(Numeric(4,3),default=0)
    occurred_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True,index=True)
    resolved_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True,index=True)
    location_city: Mapped[str|None]=mapped_column(String(100),nullable=True)
    location_district: Mapped[str|None]=mapped_column(String(100),nullable=True,index=True)
    location_zip_prefix: Mapped[str|None]=mapped_column(String(8),nullable=True,index=True)
    source_payload_json: Mapped[str|None]=mapped_column(Text,nullable=True)
    imported_at: Mapped[datetime]=mapped_column(DateTime,default=now)
    __table_args__=(UniqueConstraint("source_dataset_id","source_record_id",name="uq_public_case_source_record"),Index("ix_public_cases_dataset_kind_occurred","source_dataset_id","record_kind","occurred_at"),)


# Stage 7 business extension.  These rows remain scoped to the demo community;
# public historical records intentionally do not reference any of these tables.
class SLAPolicy(Base):
    __tablename__="sla_policies"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    name: Mapped[str]=mapped_column(String(100),unique=True)
    category: Mapped[str|None]=mapped_column(String(32),nullable=True,index=True)
    risk_level: Mapped[str|None]=mapped_column(String(16),nullable=True,index=True)
    response_minutes: Mapped[int]=mapped_column(Integer)
    processing_minutes: Mapped[int]=mapped_column(Integer)
    enabled: Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)


class MaintenanceProfile(Base):
    __tablename__="maintenance_profiles"
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id"),primary_key=True)
    employee_code: Mapped[str]=mapped_column(String(32),unique=True,index=True)
    display_name: Mapped[str]=mapped_column(String(80))
    service_area: Mapped[str]=mapped_column(String(200),default="all")
    availability_status: Mapped[str]=mapped_column(String(16),default="available",index=True)
    current_workload: Mapped[int]=mapped_column(Integer,default=0)
    enabled: Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)


class MaintenanceSkill(Base):
    __tablename__="maintenance_skills"
    code: Mapped[str]=mapped_column(String(32),primary_key=True)
    name: Mapped[str]=mapped_column(String(80),unique=True)
    enabled: Mapped[bool]=mapped_column(Boolean,default=True)


class MaintenanceProfileSkill(Base):
    __tablename__="maintenance_profile_skills"
    profile_user_id: Mapped[str]=mapped_column(ForeignKey("maintenance_profiles.user_id"),primary_key=True)
    skill_code: Mapped[str]=mapped_column(ForeignKey("maintenance_skills.code"),primary_key=True)


class AnnouncementApproval(Base):
    __tablename__="announcement_approvals"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    announcement_id: Mapped[str]=mapped_column(ForeignKey("announcements.id"),index=True)
    requested_by: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    reviewed_by: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    decision: Mapped[str]=mapped_column(String(16),default="pending",index=True)
    review_comment: Mapped[str|None]=mapped_column(Text,nullable=True)
    requested_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    reviewed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)


class Notification(Base):
    __tablename__="notifications"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    recipient_user_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    notification_type: Mapped[str]=mapped_column(String(48),index=True)
    title: Mapped[str]=mapped_column(String(160))
    content: Mapped[str]=mapped_column(Text)
    business_type: Mapped[str]=mapped_column(String(40),index=True)
    business_id: Mapped[str]=mapped_column(String(36),index=True)
    status: Mapped[str]=mapped_column(String(12),default="unread",index=True)
    idempotency_key: Mapped[str]=mapped_column(String(200),unique=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,index=True)
    read_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)


class InspectionPlan(Base):
    __tablename__="inspection_plans"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    name: Mapped[str]=mapped_column(String(120),unique=True)
    category: Mapped[str]=mapped_column(String(32),index=True)
    target_type: Mapped[str]=mapped_column(String(32))
    target_id: Mapped[str|None]=mapped_column(String(36),nullable=True,index=True)
    frequency: Mapped[str]=mapped_column(String(16),index=True)
    enabled: Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    assigned_role: Mapped[str]=mapped_column(String(32),default="maintenance")
    assignee_id: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True,index=True)
    next_run_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    created_by: Mapped[str]=mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)


class Equipment(Base):
    __tablename__="equipment"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    equipment_code: Mapped[str]=mapped_column(String(48),unique=True,index=True)
    name: Mapped[str]=mapped_column(String(120),index=True)
    category: Mapped[str]=mapped_column(String(32),index=True)
    property_id: Mapped[str|None]=mapped_column(ForeignKey("properties.id"),nullable=True,index=True)
    location: Mapped[str]=mapped_column(String(200),index=True)
    manufacturer: Mapped[str|None]=mapped_column(String(100),nullable=True)
    model: Mapped[str|None]=mapped_column(String(100),nullable=True)
    installed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    status: Mapped[str]=mapped_column(String(16),default="normal",index=True)
    last_inspection_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    next_inspection_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    enabled: Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)


class SchedulerJobRun(Base):
    __tablename__="scheduler_job_runs"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    job_name: Mapped[str]=mapped_column(String(64),index=True)
    run_key: Mapped[str]=mapped_column(String(100),unique=True)
    status: Mapped[str]=mapped_column(String(16),default="completed")
    result_json: Mapped[str|None]=mapped_column(Text,nullable=True)
    error_message: Mapped[str|None]=mapped_column(Text,nullable=True)
    started_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    finished_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
