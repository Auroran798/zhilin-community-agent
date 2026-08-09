"""One policy pipeline for local Agent and MCP tool calls.

The Harness intentionally adapts existing services instead of becoming a second
business-service layer.  It stores only redacted diagnostics locally.
"""
from __future__ import annotations
import json, re, time, uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session
from api.config import settings
from api.time import as_utc, utc_now
from api.idempotency import claim as claim_idempotency, complete as complete_idempotency, fail as fail_idempotency, fingerprint
from api.models import (Binding, Bill, ExecutionSpan, ExecutionTrace, HarnessExecution,
                        Property, User, WorkOrder, Announcement, RectificationOrder,
                        PaymentRecord, InspectionTask, InspectionPlan, Equipment)

class ExecutionContext(BaseModel):
    """Identity is created by API auth, MCP transport, or controlled tests only."""
    model_config=ConfigDict(extra="forbid")
    user_id: str
    role: str
    source: str = "local"
    request_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    trace_id: str | None = None
    community_id: str | None = None
    bound_property_ids: list[str] = Field(default_factory=list)
    confirmation_id: str | None = None
    approval_id: str | None = None
    transport: str | None = None
    client_name: str | None = None
    environment: str | None = None
    started_at: datetime | None = None
    confirmed: bool = False

class ToolResult(BaseModel):
    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, str] | None = None
    trace_id: str | None = None
    idempotent: bool = False

class ToolMeta(BaseModel):
    name: str; description: str; input_model: type[BaseModel] | None = None
    output_model: type[BaseModel] | None = ToolResult
    roles: set[str]; operation_type: str = "read"; risk: str = "low"
    requires_confirmation: bool = False; requires_staff_approval: bool = False
    permission_code: str = "property.read"; idempotency_required: bool = False
    version: str = "1.0"; schema_version: str = "1.0"; category: str = "property"
    default_timeout_seconds: int = 15; retry_policy: str = "read_once_write_never"
    audit_level: str = "standard"; contains_sensitive_data: bool = False
    replacement_tool: str | None = None
    mcp_exposed: bool = True; enabled: bool = True; deprecated: bool = False

class EmptyArgs(BaseModel): model_config=ConfigDict(extra="forbid")
class WorkOrderIdArgs(BaseModel): model_config=ConfigDict(extra="forbid"); work_order_id:str
class BillIdArgs(BaseModel): model_config=ConfigDict(extra="forbid"); bill_id:str
class AnnouncementIdArgs(BaseModel): model_config=ConfigDict(extra="forbid"); announcement_id:str
class PermissionArgs(BaseModel):
    model_config=ConfigDict(extra="forbid")
    resource_type:str=Field(min_length=2,max_length=40); resource_id:str=Field(min_length=1,max_length=80)
class CompareBillsArgs(BaseModel):
    model_config=ConfigDict(extra="forbid")
    current_bill_id:str; previous_bill_id:str
class InspectionTaskCreateArgs(BaseModel):
    model_config=ConfigDict(extra="forbid")
    area_type:str=Field(min_length=2,max_length=64); location_description:str=Field(min_length=2,max_length=200)
    scheduled_at:datetime; assignee_id:str
class AnnouncementReviewArgs(BaseModel):
    model_config=ConfigDict(extra="forbid")
    announcement_id:str
class QueryArgs(BaseModel): model_config=ConfigDict(extra="forbid"); query:str=Field(min_length=2,max_length=1000)
class PublicCaseSearchArgs(BaseModel):
    model_config=ConfigDict(extra="forbid")
    query: str | None = Field(None, min_length=2, max_length=200)
    category: str | None = Field(None, max_length=32)
    record_kind: str | None = Field(None, max_length=40)
    limit: int = Field(20, ge=1, le=100)
class AgentReadArgs(BaseModel):
    model_config=ConfigDict(extra="forbid")
    intent:str=Field(min_length=2,max_length=64)
    fields:dict[str,Any]=Field(default_factory=dict)
    text:str=Field(min_length=1,max_length=2000)
class WorkOrderAssignArgs(BaseModel): model_config=ConfigDict(extra="forbid"); work_order_id:str; assignee_id:str; note:str=""
class WorkOrderStatusArgs(BaseModel): model_config=ConfigDict(extra="forbid"); work_order_id:str; target_status:str; note:str=""; resolution:str|None=None
class RectificationStatusArgs(BaseModel): model_config=ConfigDict(extra="forbid"); rectification_id:str; target_status:str; note:str=""; resolution:str|None=None
class InspectionTaskIdArgs(BaseModel): model_config=ConfigDict(extra="forbid"); task_id:str
class RectificationIdArgs(BaseModel): model_config=ConfigDict(extra="forbid"); rectification_id:str
class EquipmentIdArgs(BaseModel): model_config=ConfigDict(extra="forbid"); equipment_id:str
class EquipmentSearchArgs(BaseModel): model_config=ConfigDict(extra="forbid"); query:str|None=None; category:str|None=None; status:str|None=None
class BillReviewIdArgs(BaseModel): model_config=ConfigDict(extra="forbid"); review_request_id:str

def _redact(value: Any) -> str:
    text=json.dumps(value,ensure_ascii=False,default=str)
    text=re.sub(r"(?<!\d)1\d{10}(?!\d)","***",text)
    text=re.sub(r'(?i)(token|password|secret|authorization)\s*[:=]\s*[^,\s}]+',r'\1=***',text)
    return text[:4000]

def _error(code:str, message:str, trace_id:str|None=None) -> ToolResult:
    return ToolResult(ok=False,error={"code":code,"message":message},trace_id=trace_id)

def _registry() -> dict[str, ToolMeta]:
    from agent.tools import (AnnouncementDraftArgs, AnnouncementDecisionArgs, AssignWorkOrderArgs, BillReviewArgs, CancelWorkOrderArgs,
        CreateWorkOrderArgs, InspectionRecordArgs, RateWorkOrderArgs, RectificationArgs, WorkOrderStatusArgs as AgentWorkOrderStatusArgs, RectificationStatusArgs as AgentRectificationStatusArgs)
    roles={"resident","customer_service","maintenance","manager"}
    read=lambda name,desc,model=EmptyArgs,allowed=roles: ToolMeta(name=name,description=desc,input_model=model,roles=allowed)
    write=lambda name,desc,model,allowed,risk="medium",permission="property.write": ToolMeta(name=name,description=desc,input_model=model,roles=allowed,operation_type="write",risk=risk,requires_confirmation=True,permission_code=permission,idempotency_required=True)
    return {
      "get_current_user_context":read("get_current_user_context","读取当前可信认证上下文，不接受工具参数伪造身份。"),
      "get_resident_profile":read("get_resident_profile","读取当前认证用户的脱敏档案。"),
      "get_bound_property":read("get_bound_property","读取当前认证用户绑定的房屋，不接受外部 property_id。"),
      "verify_user_permission":read("verify_user_permission","服务端验证当前身份对对象的权限，不返回其他居民对象是否存在。",PermissionArgs),
      "list_work_orders":read("list_work_orders","按当前认证身份读取可见工单。"),
      "list_user_work_orders":read("list_user_work_orders","按当前认证身份读取可见工单。"),
      "list_my_work_orders":read("list_my_work_orders","按当前认证身份读取可见工单。"),
      "get_work_order":read("get_work_order","读取一张有权限访问的工单。",WorkOrderIdArgs),
      "get_work_order_timeline":read("get_work_order_timeline","读取有权限工单的完整状态时间线。",WorkOrderIdArgs),
      "get_sla_status":read("get_sla_status","确定性计算工单 SLA 状态。",WorkOrderIdArgs),
      "recommend_assignee":read("recommend_assignee","基于技能、区域、负载和可用状态给出派单建议；不执行派单。",WorkOrderIdArgs,{"customer_service","manager"}),
      "get_property_bill":read("get_property_bill","读取有权限访问的模拟账单。",BillIdArgs,{"resident","customer_service","manager"}),
      "get_my_bill":read("get_my_bill","读取当前居民绑定房屋的最近账单。",allowed={"resident"}),
      "get_bill_details":read("get_bill_details","读取账单明细，只读。",BillIdArgs,{"resident","customer_service","manager"}),
      "list_payment_records":read("list_payment_records","读取账单支付记录，只读且不执行支付。",BillIdArgs,{"resident","customer_service","manager"}),
      "get_payment_history":read("get_payment_history","读取当前可见房屋的支付历史，只读。",BillIdArgs,{"resident","customer_service","manager"}),
      "get_bill_review_status":read("get_bill_review_status","读取本人或有权限的费用复核申请状态。",BillReviewIdArgs,{"resident","customer_service","manager"}),
      "compare_bills":read("compare_bills","比较两张有权限的模拟账单。",CompareBillsArgs,{"resident","customer_service","manager"}),
      "list_announcements":read("list_announcements","读取已发布公告；员工可见草稿状态。"),
      "get_announcement":read("get_announcement","读取公告详情，居民仅可见已发布公告。",AnnouncementIdArgs),
      "list_inspection_tasks":read("list_inspection_tasks","读取当前可见巡检任务。",allowed={"customer_service","maintenance","manager"}),
      "get_inspection_task":read("get_inspection_task","读取一项有权限的巡检任务。",InspectionTaskIdArgs, {"customer_service","maintenance","manager"}),
      "get_rectification_status":read("get_rectification_status","读取整改状态，居民不可访问。",allowed={"customer_service","maintenance","manager"}),
      "get_rectification_order":read("get_rectification_order","读取一张有权限的整改工单。",RectificationIdArgs,{"customer_service","maintenance","manager"}),
      "search_equipment":read("search_equipment","搜索设备台账，只读。",EquipmentSearchArgs,{"customer_service","maintenance","manager"}),
      "get_equipment":read("get_equipment","读取设备详情，只读。",EquipmentIdArgs,{"customer_service","maintenance","manager"}),
      "get_equipment_history":read("get_equipment_history","读取设备关联的报修、巡检与整改历史。",EquipmentIdArgs,{"customer_service","maintenance","manager"}),
      "query_knowledge":read("query_knowledge","在受控知识库检索并返回带来源回答。",QueryArgs),
      "search_knowledge":read("search_knowledge","检索知识证据并返回来源。",QueryArgs),
      "ask_knowledge":read("ask_knowledge","基于证据回答并返回回答状态、引用和警告。",QueryArgs),
      "search_public_real_cases":read("search_public_real_cases","仅客服/管理员读取脱敏的真实公开历史住宅维护/巡检整改案例。",PublicCaseSearchArgs,{"customer_service","manager"}),
      "agent_read":ToolMeta(name="agent_read",description="内部 Agent 只读适配器，复用阶段 3 查询语义。",input_model=AgentReadArgs,roles=roles,mcp_exposed=False),
      "create_work_order":write("create_work_order","创建本人绑定房屋报修；必须确认和幂等键。",CreateWorkOrderArgs,{"resident"},permission="work_order.create"),
      "assign_work_order":write("assign_work_order","客服/经理人工确认后正式派单。",AssignWorkOrderArgs,{"customer_service","manager"},permission="work_order.assign"),
      "update_work_order_status":write("update_work_order_status","按状态机更新有权限的工单状态。",AgentWorkOrderStatusArgs,{"resident","customer_service","maintenance","manager"},permission="work_order.transition"),
      "create_bill_review":write("create_bill_review","为本人账单创建费用核查申请；必须确认。",BillReviewArgs,{"resident"},permission="bill.review"),
      "create_bill_review_request":write("create_bill_review_request","为本人账单创建费用核查申请；必须确认。",BillReviewArgs,{"resident"},permission="bill.review"),
      "cancel_work_order":write("cancel_work_order","取消本人可取消工单；必须确认。",CancelWorkOrderArgs,{"resident"},permission="work_order.cancel"),
      "rate_work_order":write("rate_work_order","评价本人已完成工单；必须确认。",RateWorkOrderArgs,{"resident"},risk="low",permission="work_order.rate"),
      "submit_work_order_rating":write("submit_work_order_rating","评价本人已完成工单；必须确认。",RateWorkOrderArgs,{"resident"},risk="low",permission="work_order.rate"),
      "create_announcement_draft":write("create_announcement_draft","仅创建公告草稿，不能发布；必须确认。",AnnouncementDraftArgs,{"customer_service","manager"},permission="announcement.draft"),
      "submit_announcement_for_review":write("submit_announcement_for_review","提交公告进入人工审核，不会发布；必须确认。",AnnouncementReviewArgs,{"customer_service","manager"},permission="announcement.review"),
      "request_announcement_approval":write("request_announcement_approval","提交公告人工审核；不发布。",AnnouncementDecisionArgs,{"customer_service","manager"},permission="announcement.review"),
      "approve_announcement":write("approve_announcement","仅经理人工审批公告；普通 Agent 不可自动调用。",AnnouncementDecisionArgs,{"manager"},risk="high",permission="announcement.approve"),
      "publish_announcement":ToolMeta(name="publish_announcement",description="仅经理在人工确认的 API 工作流中发布已审批公告；不向 MCP/Agent 自动公开。",input_model=AnnouncementDecisionArgs,roles={"manager"},operation_type="write",risk="high",requires_confirmation=True,permission_code="announcement.publish",idempotency_required=True,mcp_exposed=False),
      "create_inspection_task":write("create_inspection_task","管理员创建巡检任务，不自动关闭重大整改。",InspectionTaskCreateArgs,{"manager"},permission="inspection.create"),
      "submit_inspection_record":write("submit_inspection_record","为本人获分派任务提交巡检记录；必须确认。",InspectionRecordArgs,{"maintenance"},permission="inspection.submit"),
      "create_rectification":write("create_rectification","创建整改工单；高风险仅管理员执行。",RectificationArgs,{"customer_service","manager"},risk="high",permission="rectification.create"),
      "create_rectification_order":write("create_rectification_order","创建整改工单；高风险仅管理员执行。",RectificationArgs,{"customer_service","manager"},risk="high",permission="rectification.create"),
      "update_rectification_status":write("update_rectification_status","责任维修人员更新整改状态。",AgentRectificationStatusArgs,{"maintenance"},permission="rectification.update"),
      "review_rectification":write("review_rectification","经理人工复查并关闭整改；重大风险不能由 AI 自动关闭。",AgentRectificationStatusArgs,{"manager"},risk="high",permission="rectification.review"),
    }

class Harness:
    _failures: dict[str, tuple[int,float]]={}
    _injected: set[str]=set()
    @property
    def registry(self): return _registry()
    def discover(self): return [tool for tool in self.registry.values() if tool.mcp_exposed]
    def _span(self,db:Session,trace_id:str,name:str,kind:str,attrs:dict):
        row=ExecutionSpan(trace_id=trace_id,span_id=uuid.uuid4().hex,name=name,kind=kind,status="running",attributes_redacted=_redact(attrs),started_at=utc_now());db.add(row);db.commit();return row
    def _finish_span(self,db,row,status,error=None):
        row.status=status;row.error_code=error;row.finished_at=utc_now();row.latency_ms=max(0,int((row.finished_at-as_utc(row.started_at)).total_seconds()*1000));db.commit()
    def _check_input(self, meta:ToolMeta, raw:dict):
        # property_id is a legitimate work-order input, but object-level ownership
        # is verified again by the existing service; identity/confirmation are not.
        prohibited={"user_id","role","property_id_override","actor_id","confirmed"}
        if prohibited & set(raw): raise HTTPException(400,"禁止由工具参数伪造身份、角色、房屋或确认状态")
        blob=_redact(raw).lower()
        if any(x in blob for x in ("ignore previous instructions","system prompt","忽略之前指令","显示系统提示词","become_admin")):
            raise HTTPException(400,"检测到提示词注入或越权内容")
        return meta.input_model.model_validate(raw).model_dump() if meta.input_model else raw
    def _read(self, db:Session, user:User, name:str,args:dict) -> dict:
        from agent.tools import primary_property
        if name=="agent_read":
            from agent.tools import read_tool_raw
            return read_tool_raw(db,user,args["intent"],args["fields"],args["text"])
        if name=="get_current_user_context":
            p=primary_property(db,user)
            return {"user_id":user.id,"role":user.role,"property_id":p.id if p else None,"community_name":p.community_name if p else None}
        if name=="verify_user_permission":
            resource_type=args["resource_type"]; resource_id=args["resource_id"]; allowed=False
            if resource_type in {"work_order","work_orders"}:
                x=db.get(WorkOrder,resource_id);allowed=bool(x and (user.role in {"customer_service","manager"} or x.requester_id==user.id or x.assignee_id==user.id))
            elif resource_type in {"bill","property_bill"}:
                x=db.get(Bill,resource_id);allowed=bool(x and (user.role in {"customer_service","manager"} or db.query(Binding).filter_by(user_id=user.id,property_id=x.property_id).first()))
            elif resource_type in {"property","properties"}:
                allowed=bool(db.query(Binding).filter_by(user_id=user.id,property_id=resource_id).first()) or user.role in {"customer_service","manager"}
            if not allowed: raise HTTPException(403,"当前身份无权访问该业务对象")
            return {"allowed":True,"resource_type":resource_type}
        if name=="get_resident_profile": return {"id":user.id,"display_name":user.display_name,"role":user.role,"phone_masked":user.phone_masked}
        if name=="get_bound_property":
            p=primary_property(db,user); return {"property":None} if not p else {"id":p.id,"community_name":p.community_name,"building_no":p.building_no,"unit_no":p.unit_no,"room_no":p.room_no}
        if name in {"list_work_orders","list_user_work_orders","list_my_work_orders"}:
            q=db.query(WorkOrder)
            if user.role=="resident":q=q.filter_by(requester_id=user.id)
            elif user.role=="maintenance":q=q.filter_by(assignee_id=user.id)
            return {"items":[{"id":x.id,"work_order_no":x.work_order_no,"status":x.status,"summary":x.summary,"priority":x.priority} for x in q.order_by(WorkOrder.created_at.desc()).limit(50)]}
        if name=="get_work_order":
            x=db.get(WorkOrder,args["work_order_id"])
            if not x: raise HTTPException(404,"工单不存在")
            if user.role=="resident" and x.requester_id!=user.id:raise HTTPException(403,"无权访问该工单")
            if user.role=="maintenance" and x.assignee_id!=user.id:raise HTTPException(403,"无权访问该工单")
            return {"id":x.id,"work_order_no":x.work_order_no,"status":x.status,"summary":x.summary,"category":x.category}
        if name=="get_work_order_timeline":
            x=db.get(WorkOrder,args["work_order_id"])
            if not x or (user.role=="resident" and x.requester_id!=user.id) or (user.role=="maintenance" and x.assignee_id!=user.id): raise HTTPException(404,"工单不存在或无权访问")
            from api.models import WorkOrderEvent
            return {"work_order_id":x.id,"items":[{"event_type":e.event_type,"from_status":e.from_status,"to_status":e.to_status,"operator_id":e.operator_id,"note":e.note,"created_at":e.created_at} for e in db.query(WorkOrderEvent).filter_by(work_order_id=x.id).order_by(WorkOrderEvent.created_at).all()]}
        if name=="get_sla_status":
            x=db.get(WorkOrder,args["work_order_id"])
            if not x or (user.role=="resident" and x.requester_id!=user.id) or (user.role=="maintenance" and x.assignee_id!=user.id): raise HTTPException(404,"工单不存在或无权访问")
            from api.stage7 import SLAService
            return SLAService.get_status(x)
        if name=="recommend_assignee":
            x=db.get(WorkOrder,args["work_order_id"])
            if not x:raise HTTPException(404,"工单不存在")
            from api.stage7 import AssignmentService
            return AssignmentService.recommend(db,x)
        if name=="get_property_bill":
            x=db.get(Bill,args["bill_id"])
            if not x:raise HTTPException(404,"账单不存在")
            if user.role=="resident" and not db.query(Binding).filter_by(user_id=user.id,property_id=x.property_id).first():raise HTTPException(403,"无权访问该账单")
            return {"id":x.id,"bill_no":x.bill_no,"billing_period":x.billing_period,"amount":str(x.amount),"status":x.status}
        if name=="get_my_bill":
            from agent.tools import primary_property
            prop=primary_property(db,user)
            if not prop: return {"items":[]}
            rows=db.query(Bill).filter_by(property_id=prop.id).order_by(Bill.billing_period.desc()).limit(24).all()
            return {"items":[{"id":x.id,"bill_no":x.bill_no,"billing_period":x.billing_period,"amount":str(x.amount),"status":x.status} for x in rows]}
        if name=="get_bill_details":
            from api.stage7 import BillingService
            data=BillingService.details(db,user,args["bill_id"])
            return {"bill_id":data["bill"].id,"items":[{"item_name":x.item_name,"item_type":x.item_type,"amount":str(x.amount),"description":x.description} for x in data["items"]],"paid_amount":str(data["paid_amount"]),"balance":str(data["balance"])}
        if name=="list_payment_records":
            x=db.get(Bill,args["bill_id"])
            if not x: raise HTTPException(404,"账单不存在")
            if user.role=="resident" and not db.query(Binding).filter_by(user_id=user.id,property_id=x.property_id).first(): raise HTTPException(403,"无权访问该账单")
            return {"bill_id":x.id,"items":[{"id":p.id,"amount":str(p.amount),"paid_at":p.paid_at,"method":p.payment_channel,"status":p.status} for p in db.query(PaymentRecord).filter_by(bill_id=x.id).all()]}
        if name=="get_payment_history":
            from api.stage7 import BillingService
            x=db.get(Bill,args["bill_id"])
            if not x:raise HTTPException(404,"账单不存在")
            return {"items":[{"id":p.id,"bill_id":p.bill_id,"amount":str(p.amount),"paid_at":p.paid_at,"status":p.status} for p in BillingService.payment_history(db,user,x.property_id)]}
        if name=="get_bill_review_status":
            from api.models import BillReviewRequest
            x=db.get(BillReviewRequest,args["review_request_id"])
            if not x or (user.role=="resident" and x.resident_id!=user.id):raise HTTPException(404,"费用复核申请不存在或无权访问")
            return {"id":x.id,"request_no":x.request_no,"status":x.status,"result":x.result,"handled_at":x.handled_at}
        if name=="compare_bills":
            from skills.billing import compare as compare_bill
            current=db.get(Bill,args["current_bill_id"]);previous=db.get(Bill,args["previous_bill_id"])
            if not current or not previous: raise HTTPException(404,"账单不存在")
            for x in (current,previous):
                if user.role=="resident" and not db.query(Binding).filter_by(user_id=user.id,property_id=x.property_id).first(): raise HTTPException(403,"无权访问该账单")
            return compare_bill(current.amount,previous.amount)
        if name=="list_announcements":
            q=db.query(Announcement);q=q.filter_by(status="published") if user.role=="resident" else q
            return {"items":[{"id":x.id,"title":x.title,"status":x.status,"scope":x.affected_scope} for x in q.order_by(Announcement.created_at.desc()).limit(50)]}
        if name=="get_announcement":
            x=db.get(Announcement,args["announcement_id"])
            if not x or (user.role=="resident" and x.status!="published"): raise HTTPException(404,"公告不存在")
            return {"id":x.id,"title":x.title,"content":x.content,"status":x.status,"scope":x.affected_scope}
        if name=="get_rectification_status":
            q=db.query(RectificationOrder);q=q.filter_by(assignee_id=user.id) if user.role=="maintenance" else q
            return {"items":[{"id":x.id,"rectification_no":x.rectification_no,"status":x.status,"risk_level":x.risk_level} for x in q.limit(50)]}
        if name=="list_inspection_tasks":
            q=db.query(InspectionTask)
            if user.role=="maintenance":q=q.filter_by(assignee_id=user.id)
            return {"items":[{"id":x.id,"task_no":x.task_no,"status":x.status,"area_type":x.area_type,"scheduled_at":x.scheduled_at} for x in q.order_by(InspectionTask.scheduled_at.desc()).limit(50)]}
        if name=="get_inspection_task":
            x=db.get(InspectionTask,args["task_id"])
            if not x or (user.role=="maintenance" and x.assignee_id!=user.id):raise HTTPException(404,"巡检任务不存在或无权访问")
            return {"id":x.id,"task_no":x.task_no,"status":x.status,"area_type":x.area_type,"location_description":x.location_description}
        if name=="get_rectification_order":
            x=db.get(RectificationOrder,args["rectification_id"])
            if not x or (user.role=="maintenance" and x.assignee_id!=user.id):raise HTTPException(404,"整改工单不存在或无权访问")
            return {"id":x.id,"rectification_no":x.rectification_no,"status":x.status,"risk_level":x.risk_level,"deadline":x.deadline}
        if name=="search_equipment":
            q=db.query(Equipment)
            if args.get("query"):q=q.filter((Equipment.name.contains(args["query"]))|(Equipment.equipment_code.contains(args["query"]))|(Equipment.location.contains(args["query"])))
            if args.get("category"):q=q.filter_by(category=args["category"])
            if args.get("status"):q=q.filter_by(status=args["status"])
            return {"items":[{"id":x.id,"equipment_code":x.equipment_code,"name":x.name,"category":x.category,"location":x.location,"status":x.status} for x in q.limit(50)]}
        if name in {"get_equipment","get_equipment_history"}:
            from api.stage7 import EquipmentService
            data=EquipmentService.history(db,args["equipment_id"])
            if name=="get_equipment":
                x=data["equipment"];return {"id":x.id,"equipment_code":x.equipment_code,"name":x.name,"category":x.category,"location":x.location,"status":x.status}
            return {"equipment_id":data["equipment"].id,"work_orders":[{"id":x.id,"work_order_no":x.work_order_no,"status":x.status} for x in data["work_orders"]],"inspection_tasks":[{"id":x.id,"task_no":x.task_no,"status":x.status} for x in data["inspection_tasks"]],"rectifications":[{"id":x.id,"rectification_no":x.rectification_no,"status":x.status} for x in data["rectifications"]]}
        if name in {"query_knowledge","search_knowledge","ask_knowledge"}:
            from agent.tools import primary_property
            from rag.service import search
            p=primary_property(db,user);result=search(db,args["query"],user,p.community_name if p else None)
            if name=="search_knowledge": return {"evidence":result.get("citations",[]),"answer_status":result.get("answer_status"),"warnings":result.get("warnings",[])}
            return result
        if name=="search_public_real_cases":
            from api.models import PublicCase
            if settings.data_mode!="public_real": raise HTTPException(503,"真实公开数据模式未启用")
            q=db.query(PublicCase)
            if args.get("category"): q=q.filter_by(normalized_category=args["category"])
            if args.get("record_kind"): q=q.filter_by(record_kind=args["record_kind"])
            if args.get("query"): q=q.filter(PublicCase.sanitized_text.contains(args["query"]))
            items=q.order_by(PublicCase.occurred_at.desc()).limit(args["limit"]).all()
            return {"mode":"public_real","items":[{"id":x.id,"source_dataset_id":x.source_dataset_id,"source_record_id":x.source_record_id,"record_kind":x.record_kind,"category":x.normalized_category,"risk_level":x.risk_level,"status":x.normalized_status,"sanitized_text":x.sanitized_text,"occurred_at":x.occurred_at,"source_url":x.source_url} for x in items],"notice":"Historical public regulatory records; not current property status."}
        raise HTTPException(400,"未注册只读工具")
    def execute(self,db:Session,ctx:ExecutionContext,name:str,raw:dict,idempotency_key:str|None=None,backend="local")->ToolResult:
        trace_id=ctx.trace_id or f"tr-{uuid.uuid4().hex}"
        trace=ExecutionTrace(trace_id=trace_id,request_id=ctx.request_id,session_id=ctx.session_id,run_id=ctx.run_id,user_id=ctx.user_id,outcome="running");db.add(trace);db.commit()
        span=self._span(db,trace_id,"harness.execute","harness",{"tool":name,"backend":backend,"source":ctx.source})
        meta=self.registry.get(name)
        started=time.perf_counter(); execution=None; idem_record=None
        try:
            if not meta or (ctx.source.startswith("mcp") and not meta.mcp_exposed): raise HTTPException(404,"工具不存在或未启用")
            user=db.get(User,ctx.user_id)
            if not user or not user.is_active or user.role!=ctx.role:raise HTTPException(401,"认证上下文无效")
            if ctx.role not in meta.roles:raise HTTPException(403,"当前角色无权调用该工具")
            args=self._check_input(meta,raw)
            if meta.requires_confirmation and not ctx.confirmed: raise HTTPException(409,"写操作需要由受信任工作流明确确认")
            if name=="create_rectification" and args.get("risk_level") in {"high","critical"} and ctx.role!="manager":raise HTTPException(403,"高风险整改须由管理员人工审批")
            if meta.idempotency_required and not idempotency_key:
                raise HTTPException(400,"写工具必须提供非空 Idempotency-Key")
            key=idempotency_key
            idem_record,replay=claim_idempotency(db,user,f"harness.tool.{name}",key,args)
            execution=HarnessExecution(trace_id=trace_id,tool_name=name,backend=backend,actor_id=user.id,operation_type=meta.operation_type,idempotency_key=fingerprint(key) if key else None,attempt=1,status="running",input_redacted=_redact(args));db.add(execution);db.commit()
            if replay:
                result=json.loads(idem_record.response_json or "{}")
                execution.status="completed";execution.output_redacted=_redact(result);execution.latency_ms=int((time.perf_counter()-started)*1000);db.commit()
                trace.outcome="success";trace.finished_at=utc_now();db.commit();self._finish_span(db,span,"completed")
                return ToolResult(ok=True,data=result,trace_id=trace_id,idempotent=True)
            failure_key=f"{name}:{ctx.user_id}"
            count,opened=self._failures.get(failure_key,(0,0))
            if count>=settings.harness_circuit_failure_threshold and time.time()-opened<settings.harness_circuit_reset_seconds: raise HTTPException(503,"工具暂时熔断，请稍后重试")
            attempts=1 if meta.operation_type=="write" else settings.harness_read_retries+1
            last=None
            for attempt in range(1,attempts+1):
                if attempt>1:
                    execution=HarnessExecution(trace_id=trace_id,tool_name=name,backend=backend,actor_id=user.id,operation_type=meta.operation_type,idempotency_key=fingerprint(key) if key else None,attempt=attempt,status="running",input_redacted=_redact(args));db.add(execution);db.commit()
                else:
                    execution.attempt=attempt;db.commit()
                try:
                    if settings.harness_failure_injection=="transient_read_once" and meta.operation_type=="read" and failure_key not in self._injected:
                        self._injected.add(failure_key);raise HTTPException(503,"TEMPORARY_DEPENDENCY")
                    if meta.operation_type=="read": result=self._read(db,user,name,args)
                    else:
                        from agent.tools import execute_raw
                        action={"action":name,**args};result=execute_raw(db,user,action,key,ctx.run_id)
                        complete_idempotency(idem_record,name,str(result.get("id") or result.get("work_order_id") or trace_id),result)
                        db.commit()
                        if settings.harness_failure_injection=="unknown_after_write" and failure_key not in self._injected:
                            self._injected.add(failure_key)
                            # The write is durable and replayable. The caller must
                            # retry explicitly with the same key to learn its result.
                            raise HTTPException(504,"UNKNOWN_OUTCOME")
                    if time.perf_counter()-started > settings.harness_default_timeout_seconds:
                        # A completed write may have reached the database.  It is
                        # deliberately not retried; its idempotency key is the only
                        # permitted recovery path on the next explicit request.
                        raise HTTPException(504,"UNKNOWN_OUTCOME" if meta.operation_type=="write" else "TOOL_TIMEOUT")
                    break
                except HTTPException as exc:
                    last=exc
                    if meta.operation_type=="read" and exc.status_code in {502,503,504} and attempt<attempts:
                        execution.status="retryable_failed";execution.error_code="TEMPORARY_DEPENDENCY";execution.latency_ms=int((time.perf_counter()-started)*1000);db.commit();continue
                    raise
            if meta.operation_type=="write":
                complete_idempotency(idem_record,name,str(result.get("id") or result.get("work_order_id") or trace_id),result)
            execution.status="completed";execution.output_redacted=_redact(result);execution.latency_ms=int((time.perf_counter()-started)*1000);db.commit()
            trace.outcome="success";trace.finished_at=utc_now();db.commit();self._failures.pop(failure_key,None);self._finish_span(db,span,"completed")
            return ToolResult(ok=True,data=result,trace_id=trace_id,idempotent=bool(result.get("idempotent")))
        except (HTTPException,ValidationError) as exc:
            status=getattr(exc,"status_code",400);detail=str(getattr(exc,"detail",exc));code="VALIDATION_ERROR" if isinstance(exc,ValidationError) or status==400 else "UNAUTHORIZED" if status==401 else "FORBIDDEN" if status==403 else "CONFIRMATION_REQUIRED" if status==409 else "NOT_FOUND" if status==404 else "TOOL_UNAVAILABLE" if status>=500 else "TOOL_FAILED"
            if execution:
                fail_idempotency(idem_record);execution.status="failed";execution.error_code=code;execution.latency_ms=int((time.perf_counter()-started)*1000);db.commit()
            self._failures[f"{name}:{ctx.user_id}"]=(self._failures.get(f"{name}:{ctx.user_id}",(0,time.time()))[0]+(1 if status>=500 else 0),time.time())
            trace.outcome="failed";trace.error_code=code;trace.finished_at=utc_now();db.commit();self._finish_span(db,span,"failed",code)
            return _error(code,detail,trace_id)
        except Exception:
            if execution: fail_idempotency(idem_record);execution.status="failed";execution.error_code="INTERNAL_ERROR";db.commit()
            trace.outcome="failed";trace.error_code="INTERNAL_ERROR";trace.finished_at=utc_now();db.commit();self._finish_span(db,span,"failed","INTERNAL_ERROR")
            return _error("INTERNAL_ERROR","工具执行失败，未报告为成功。",trace_id)

_instance=Harness()
def get_harness()->Harness:return _instance
