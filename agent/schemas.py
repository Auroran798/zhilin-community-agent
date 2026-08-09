from typing import Any, Literal
from pydantic import BaseModel, Field

Intent = Literal[
    "repair_request", "work_order_query", "knowledge_question", "bill_query",
    "bill_explanation", "bill_review_request", "announcement_query",
    "announcement_draft", "inspection_report", "rectification_query",
    "work_order_rating", "external_work_order_query", "public_real_case_query", "equipment_query", "human_service", "out_of_scope",
]

class IntentResult(BaseModel):
    intent: Intent
    confidence: float = Field(ge=0, le=1)

class ExtractedFields(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)

class AgentMessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

class ConfirmationIn(BaseModel):
    decision: Literal["confirm", "cancel"]

class ConfirmationModifyIn(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)

class ResumeIn(BaseModel):
    message: str | None = Field(default=None, max_length=2000)

class MemoryIn(BaseModel):
    memory_key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    value: str = Field(min_length=1, max_length=500)
    memory_type: Literal["preference", "notification_preference", "service_preference"] = "preference"
    consented: bool

class ReviewAssignIn(BaseModel):
    assignee_id: str

class ReviewResolveIn(BaseModel):
    result: str = Field(min_length=1, max_length=2000)
