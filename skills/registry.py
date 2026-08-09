from __future__ import annotations
from .base import SkillSpec

SPECS=(
 SkillSpec("repair",("repair_request",),("location_description","fault_description"),False,True,False,("create_work_order",),{"location_description":"请问故障发生在什么具体位置？","fault_description":"请描述故障现象。"}),
 SkillSpec("work_order",("work_order_query","work_order_rating","external_work_order_query","public_real_case_query"),(),False,True,False,("list_work_orders","list_external_work_orders","search_public_real_cases","cancel_work_order","submit_work_order_rating"),{}),
 SkillSpec("knowledge",("knowledge_question",),(),True,False,False,("ask_knowledge",),{}),
 SkillSpec("billing",("bill_query","bill_explanation","bill_review_request"),(),True,True,False,("get_property_bill","list_payment_records","compare_bills","create_bill_review_request"),{}),
 SkillSpec("announcement",("announcement_query","announcement_draft"),("title","affected_scope"),False,True,True,("list_announcements","create_announcement_draft","submit_announcement_for_review"),{"title":"请补充公告标题。","affected_scope":"请补充公告影响范围。"}),
 SkillSpec("inspection",("inspection_report","rectification_query"),(),False,True,False,("submit_inspection_record","create_rectification_order","get_rectification_status"),{}),
 SkillSpec("equipment",("equipment_query",),(),False,False,False,("search_equipment","get_equipment","get_equipment_history"),{}),
 SkillSpec("human_service",("human_service",),(),False,False,True,(),{}),
 SkillSpec("out_of_scope",("out_of_scope",),(),False,False,False,(),{}),
)
BY_INTENT={intent:spec for spec in SPECS for intent in spec.intents}
def get_skill(intent: str) -> SkillSpec: return BY_INTENT.get(intent,BY_INTENT["out_of_scope"])
def names() -> set[str]: return {spec.name for spec in SPECS}
