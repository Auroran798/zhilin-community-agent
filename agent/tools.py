"""Explicit, auditable adapters to Stage 1/2 services; no internal HTTP callbacks."""
from __future__ import annotations
import json, time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from api.models import (AgentToolCall, Announcement, Bill, BillReviewRequest, Binding,
    InspectionRecord, InspectionTask, PaymentRecord, Property, RectificationOrder,
    User, WorkOrder, WorkOrderRating)
from api.schemas import WorkOrderIn
from api.services import WorkOrderService, audit, number
from api.time import utc_now
from api.idempotency import claim as claim_idempotency, complete as complete_idempotency, storage_key as idempotency_storage_key, fingerprint
from api.stage7 import AnnouncementService, AssignmentService, BillingService, EquipmentService, InspectionService, SLAService, notify
from rag.service import search
from skills.announcement import draft as announcement_draft
from skills.billing import compare as compare_bill

WRITE_ACTIONS={"create_work_order","cancel_work_order","rate_work_order","create_bill_review","create_announcement_draft","submit_announcement_review","submit_inspection_record","create_rectification"}

class CreateWorkOrderArgs(BaseModel):
    property_id:str; summary:str=Field(min_length=2,max_length=500); category:str; location_description:str=Field(min_length=2,max_length=200); fault_description:str=Field(min_length=2,max_length=2000)
class BillReviewArgs(BaseModel): bill_id:str; reason:str=Field(min_length=2,max_length=2000)
class AnnouncementDraftArgs(BaseModel): title:str=Field(min_length=2,max_length=160); content:str=Field(min_length=2,max_length=5000); affected_scope:str=Field(min_length=2,max_length=160)
class RectificationArgs(BaseModel): inspection_record_id:str; description:str=Field(min_length=2,max_length=2000); risk_level:str="medium"
class InspectionRecordArgs(BaseModel): task_id:str; description:str=Field(min_length=2,max_length=2000); abnormal:bool=True; risk_level:str="medium"
class WorkOrderStatusArgs(BaseModel): work_order_id:str; target_status:str; note:str=""; resolution:str|None=None
class AnnouncementDecisionArgs(BaseModel): announcement_id:str; review_comment:str|None=None
class AssignWorkOrderArgs(BaseModel): work_order_id:str; assignee_id:str; note:str=""
class RectificationStatusArgs(BaseModel): rectification_id:str; target_status:str; note:str=""; resolution:str|None=None
class CancelWorkOrderArgs(BaseModel): work_order_id:str
class RateWorkOrderArgs(BaseModel): work_order_id:str; score:int=Field(ge=1,le=5); comment:str|None=None
TOOL_SCHEMAS={"create_work_order":CreateWorkOrderArgs,"create_bill_review":BillReviewArgs,"create_announcement_draft":AnnouncementDraftArgs,"create_rectification":RectificationArgs,"submit_inspection_record":InspectionRecordArgs,"cancel_work_order":CancelWorkOrderArgs,"rate_work_order":RateWorkOrderArgs,"assign_work_order":AssignWorkOrderArgs,"update_work_order_status":WorkOrderStatusArgs,"request_announcement_approval":AnnouncementDecisionArgs,"approve_announcement":AnnouncementDecisionArgs,"publish_announcement":AnnouncementDecisionArgs,"update_rectification_status":RectificationStatusArgs,"review_rectification":RectificationStatusArgs}

def primary_property(db:Session,user:User):
    b=db.query(Binding).filter_by(user_id=user.id,is_primary=True).first() or db.query(Binding).filter_by(user_id=user.id).first()
    return db.get(Property,b.property_id) if b else None
def _own_property(db,user,property_id):
    if user.role=="resident" and not db.query(Binding).filter_by(user_id=user.id,property_id=property_id).first(): raise HTTPException(403,"无权访问该房屋数据")
def _redact(data:Any):
    raw=json.dumps(data,ensure_ascii=False,default=str)
    return raw.replace("password","***").replace("token","***")[:4000]
def _tool_call(db,run_id,name,args,key,fn):
    started=time.perf_counter(); row=AgentToolCall(run_id=run_id,tool_name=name,arguments_redacted=_redact(args),idempotency_key=fingerprint(key) if key else None,status="running",created_at=utc_now());db.add(row);db.commit()
    try:
        result=fn();row.status="completed";row.result_summary=_redact(result);return result
    except Exception as exc:
        row.status="failed";row.error_code=getattr(exc,"detail",str(exc))[:64];raise
    finally:
        row.latency_ms=int((time.perf_counter()-started)*1000);row.finished_at=utc_now();db.commit()

def read_tool_raw(db:Session,user:User,intent:str,fields:dict,text:str):
    prop=primary_property(db,user)
    if intent=="public_real_case_query":
        from api.config import settings
        from api.models import PublicCase
        if user.role not in {"customer_service","manager"}: raise HTTPException(403,"仅客服或管理员可查询真实公开历史案例")
        if settings.data_mode!="public_real": raise HTTPException(503,"真实公开数据模式未启用")
        q=db.query(PublicCase)
        category=next((name for name in ("电梯","给排水","公共照明","门禁","消防设施","停车","装修扰民","公共区域卫生","配电设施","道路和地面","绿化","其他") if name in text),None)
        if category: q=q.filter_by(normalized_category=category)
        items=q.order_by(PublicCase.occurred_at.desc()).limit(20).all()
        audit(db,user,"agent_search_public_real_cases","public_case",None,request_id="stage6-public-real-agent");db.commit()
        return {"tool":"search_public_real_cases","result":{"mode":"public_real","items":[{"id":x.id,"source_dataset_id":x.source_dataset_id,"source_record_id":x.source_record_id,"record_kind":x.record_kind,"category":x.normalized_category,"risk_level":x.risk_level,"status":x.normalized_status,"sanitized_text":x.sanitized_text,"occurred_at":x.occurred_at,"source_url":x.source_url} for x in items],"notice":"Historical public regulatory records only; no exact address or original raw text is returned."}}
    if intent=="external_work_order_query":
        # Stage 6 upstream data is staff-only, opt-in and read-only.  Do not
        # fall back to local data or model memory when the upstream is absent.
        from api.config import settings
        from domain.property_system import AdapterUnavailable, get_property_system_adapter
        if user.role!="manager": raise HTTPException(403,"仅管理员可查询外部物业系统工单")
        if not settings.stage6_readonly_integration_enabled: raise HTTPException(503,"阶段6只读接入未启用")
        try:
            items,total=get_property_system_adapter().list_work_orders(limit=20)
        except AdapterUnavailable as exc:
            raise HTTPException(503,"外部物业系统不可用；未推断或伪造工单数据") from exc
        audit(db,user,"agent_list_external_work_orders","external_work_order",None,request_id="stage6-readonly-agent")
        db.commit()
        return {"tool":"list_external_work_orders","result":{"items":[item.model_dump(mode="json") for item in items],"total":total,"mode":"read_only"}}
    if intent=="knowledge_question": return {"tool":"query_rag","result":search(db,text,user,prop.community_name if prop else None)}
    if intent in {"work_order_query","work_order_rating"}:
        q=db.query(WorkOrder)
        if user.role=="resident": q=q.filter_by(requester_id=user.id)
        elif user.role=="maintenance": q=q.filter_by(assignee_id=user.id)
        return {"tool":"list_work_orders","result":{"items":[{"id":x.id,"work_order_no":x.work_order_no,"status":x.status,"summary":x.summary,"priority":x.priority} for x in q.order_by(WorkOrder.created_at.desc()).limit(20)]}}
    if intent in {"bill_query","bill_explanation"}:
        q=db.query(Bill)
        if user.role=="resident": q=q.filter_by(property_id=prop.id) if prop else q.filter(False)
        items=[]
        for x in q.order_by(Bill.billing_period.desc()).limit(24):
            paid=sum((p.amount for p in db.query(PaymentRecord).filter_by(bill_id=x.id)),Decimal("0"));items.append({"id":x.id,"bill_no":x.bill_no,"billing_period":x.billing_period,"amount":str(x.amount),"paid_amount":str(paid),"balance":str(Decimal(x.amount)-paid),"status":x.status})
        result={"items":items}
        if intent=="bill_explanation":
            if len(items)<2:
                result.update({"explanation_status":"insufficient_data","message":"当前没有足够的连续账单，无法可靠比较。可申请费用核查。","offer_review":True})
            else:
                current,previous=items[0],items[1];comparison=compare_bill(Decimal(current["amount"]),Decimal(previous["amount"]))
                evidence=search(db,"物业费 收费说明 计费规则",user,prop.community_name if prop else None)
                result.update({"comparison":comparison,"explanation_status":"explained" if evidence.get("answer_status")=="answered" else "insufficient_basis","rule_answer":evidence.get("answer"),"citations":evidence.get("citations",[]),"offer_review":evidence.get("answer_status")!="answered"})
        return {"tool":"get_bill_bundle","result":result}
    if intent=="announcement_query":
        q=db.query(Announcement);q=q.filter_by(status="published") if user.role=="resident" else q
        return {"tool":"list_announcements","result":{"items":[{"id":a.id,"title":a.title,"status":a.status,"scope":a.affected_scope} for a in q.order_by(Announcement.created_at.desc()).limit(20)]}}
    if intent=="rectification_query":
        if user.role=="resident": raise HTTPException(403,"居民无权查看整改任务")
        q=db.query(RectificationOrder);q=q.filter_by(assignee_id=user.id) if user.role=="maintenance" else q
        return {"tool":"get_rectification_status","result":{"items":[{"id":x.id,"rectification_no":x.rectification_no,"status":x.status,"risk_level":x.risk_level} for x in q.limit(30)]}}
    if intent=="equipment_query":
        if user.role not in {"customer_service","maintenance","manager"}: raise HTTPException(403,"居民无权访问设备台账")
        q=db.query(__import__("api.models",fromlist=["Equipment"]).Equipment).filter_by(enabled=True)
        items=q.order_by(__import__("api.models",fromlist=["Equipment"]).Equipment.created_at.desc()).limit(30).all()
        return {"tool":"search_equipment","result":{"items":[{"id":x.id,"equipment_code":x.equipment_code,"name":x.name,"category":x.category,"location":x.location,"status":x.status} for x in items]}}
    return {"tool":None,"result":{}}

def preview(db:Session,user:User,intent:str,fields:dict)->dict|None:
    prop=primary_property(db,user)
    if intent=="repair_request" and prop:
        return {"action":"create_work_order","property_id":prop.id,"property_label":f"{prop.building_no}号楼{prop.unit_no}单元{prop.room_no}","summary":fields.get("summary", "物业报修"),"category":fields.get("category","其他"),"location_description":fields.get("location_description","待补充"),"fault_description":fields.get("fault_description",fields.get("original_description",""))}
    if intent=="bill_review_request" and prop:
        bill=db.query(Bill).filter_by(property_id=prop.id).order_by(Bill.billing_period.desc()).first()
        if bill:return {"action":"create_bill_review","bill_id":bill.id,"bill_no":bill.bill_no,"reason":fields.get("reason") or fields.get("original_description","")}
    if intent=="work_order_query" and fields.get("operation")=="cancel":
        q=db.query(WorkOrder).filter_by(requester_id=user.id)
        item=q.filter_by(work_order_no=fields["work_order_no"]).first() if fields.get("work_order_no") else q.filter(WorkOrder.status.in_(["待受理","已受理"])) .order_by(WorkOrder.created_at.desc()).first()
        if item:return {"action":"cancel_work_order","work_order_id":item.id,"work_order_no":item.work_order_no,"status":item.status}
    if intent=="work_order_rating" and user.role=="resident":
        q=db.query(WorkOrder).filter_by(requester_id=user.id,status="已完成")
        item=q.filter_by(work_order_no=fields["work_order_no"]).first() if fields.get("work_order_no") else q.order_by(WorkOrder.completed_at.desc()).first()
        if item and not db.query(WorkOrderRating).filter_by(work_order_id=item.id).first() and fields.get("score"):
            return {"action":"rate_work_order","work_order_id":item.id,"work_order_no":item.work_order_no,"score":int(fields["score"]),"comment":fields.get("comment")}
    if intent=="announcement_draft" and user.role in {"customer_service","manager"}:
        drafted=announcement_draft(fields)
        return {"action":"create_announcement_draft","title":fields.get("title","物业服务通知"),"content":drafted["formal_content"],"group_content":drafted["group_content"],"affected_scope":fields.get("affected_scope","全体业主"),"announcement_type":fields.get("announcement_type","notice")}
    if intent=="inspection_report" and user.role=="maintenance":
        task=db.query(InspectionTask).filter_by(assignee_id=user.id,status="assigned").order_by(InspectionTask.created_at.desc()).first()
        if task:return {"action":"submit_inspection_record","task_id":task.id,"task_no":task.task_no,"description":fields.get("description") or fields.get("original_description","巡检异常"),"abnormal":str(fields.get("abnormal","true")).lower()!="false","risk_level":fields.get("risk_level","medium")}
    if intent=="inspection_report" and user.role in {"customer_service","manager"} and fields.get("inspection_record_id"):
        return {"action":"create_rectification","inspection_record_id":fields["inspection_record_id"],"description":fields.get("original_description","现场隐患待整改"),"risk_level":fields.get("risk_level","medium")}
    return None

def execute_raw(db:Session,user:User,action:dict,idempotency_key:str,run_id:str|None=None)->dict:
    aliases={"create_bill_review_request":"create_bill_review","submit_work_order_rating":"rate_work_order","create_rectification_order":"create_rectification"}
    name=aliases.get(action.get("action"),action.get("action")); args={k:v for k,v in action.items() if k not in {"action","property_label","bill_no"}}
    if name in TOOL_SCHEMAS: args=TOOL_SCHEMAS[name].model_validate(args).model_dump()
    def work():
        if name=="create_inspection_task":
            if user.role!="manager":raise HTTPException(403,"仅管理员可创建巡检任务")
            old=db.query(InspectionTask).filter_by(task_no=args.get("task_no")).first() if args.get("task_no") else None
            if old:return {"inspection_task_id":old.id,"task_no":old.task_no,"status":old.status,"idempotent":True}
            task=InspectionTask(task_no=number("IT",db,InspectionTask),area_type=args["area_type"],location_description=args["location_description"],scheduled_at=args["scheduled_at"],assignee_id=args["assignee_id"],created_by=user.id);db.add(task);audit(db,user,"create_inspection_task","inspection_task",task.id);db.commit();return {"inspection_task_id":task.id,"task_no":task.task_no,"status":task.status}
        if name=="assign_work_order":
            if user.role not in {"customer_service","manager"}:raise HTTPException(403,"仅客服或管理员可人工派单")
            item=db.get(WorkOrder,args["work_order_id"])
            if not item:raise HTTPException(404,"工单不存在")
            item=AssignmentService.assign(db,user,item,args["assignee_id"],args.get("note", ""));return {"work_order_id":item.id,"work_order_no":item.work_order_no,"status":item.status,"assignee_id":item.assignee_id}
        if name=="update_work_order_status":
            item=db.get(WorkOrder,args["work_order_id"])
            if not item:raise HTTPException(404,"工单不存在")
            item=WorkOrderService().change(db,user,item,args["target_status"],args.get("note", ""),args.get("resolution"));return {"work_order_id":item.id,"status":item.status}
        if name=="submit_announcement_for_review":
            if user.role not in {"customer_service","manager"}:raise HTTPException(403,"无权提交公告审核")
            item=db.get(Announcement,args["announcement_id"])
            if not item or item.created_by!=user.id and user.role!="manager":raise HTTPException(403,"无权操作该公告")
            if item.status=="pending_review":return {"announcement_id":item.id,"status":item.status,"idempotent":True}
            if item.status!="draft":raise HTTPException(400,"仅草稿可提交审核")
            item.status="pending_review";audit(db,user,"submit_announcement_for_review","announcement",item.id);db.commit();return {"announcement_id":item.id,"status":item.status}
        if name=="request_announcement_approval":
            if user.role not in {"customer_service","manager"}:raise HTTPException(403,"无权提交公告审核")
            item=db.get(Announcement,args["announcement_id"])
            if not item or (item.created_by!=user.id and user.role!="manager"):raise HTTPException(403,"无权操作该公告")
            item=AnnouncementService.submit(db,user,item);return {"announcement_id":item.id,"status":item.status}
        if name=="approve_announcement":
            if user.role!="manager":raise HTTPException(403,"仅经理可人工审批公告")
            item=db.get(Announcement,args["announcement_id"])
            if not item:raise HTTPException(404,"公告不存在")
            item=AnnouncementService.approve(db,user,item,"approved",args.get("review_comment"));return {"announcement_id":item.id,"status":item.status}
        if name=="publish_announcement":
            if user.role!="manager":raise HTTPException(403,"仅经理可人工发布公告")
            item=db.get(Announcement,args["announcement_id"])
            if not item:raise HTTPException(404,"公告不存在")
            item=AnnouncementService.publish(db,user,item);return {"announcement_id":item.id,"status":item.status}
        if name=="create_work_order":
            if user.role!="resident":raise HTTPException(403,"仅居民可提交报修")
            _own_property(db,user,args["property_id"]); p=WorkOrderIn(property_id=args["property_id"],original_description=args["fault_description"],summary=args["summary"],category=args["category"],location_description=args["location_description"],fault_description=args["fault_description"])
            item=WorkOrderService().create(db,user,p,idempotency_key);return {"work_order_id":item.id,"work_order_no":item.work_order_no,"status":item.status}
        if name=="create_bill_review":
            if user.role!="resident":raise HTTPException(403,"仅居民可申请费用核查")
            bill=db.get(Bill,args["bill_id"]);_own_property(db,user,bill.property_id) if bill else (_ for _ in ()).throw(HTTPException(404,"账单不存在"))
            operation="bill_review.create";idem,replay=claim_idempotency(db,user,operation,idempotency_key,{"bill_id":bill.id,"reason":args["reason"]})
            if replay:
                old=db.get(BillReviewRequest,idem.resource_id)
                if not old or old.resident_id!=user.id:raise HTTPException(409,"幂等结果不存在或不属于当前用户")
                return {"review_request_id":old.id,"request_no":old.request_no,"status":old.status,"idempotent":True}
            item=BillReviewRequest(request_no=number("BR",db,BillReviewRequest),bill_id=bill.id,resident_id=user.id,reason=args["reason"],idempotency_key=idempotency_storage_key(user.id,operation,idempotency_key));db.add(item);db.flush();complete_idempotency(idem,"bill_review",item.id);audit(db,user,"create_bill_review","bill_review",item.id);db.commit();return {"review_request_id":item.id,"request_no":item.request_no,"status":item.status}
        if name=="create_announcement_draft":
            if user.role not in {"customer_service","manager"}:raise HTTPException(403,"无权创建公告草稿")
            item=Announcement(title=args["title"],announcement_type=action.get("announcement_type","notice"),content=args["content"],affected_scope=args["affected_scope"],contact_information="物业服务中心",publisher_unit="物业服务中心",created_by=user.id);db.add(item);audit(db,user,"agent_create_announcement_draft","announcement",item.id);db.commit();return {"announcement_id":item.id,"status":item.status,"formal_content":item.content,"group_content":action.get("group_content"),"notice":"仅草稿，仍需人工审核和发布"}
        if name=="submit_inspection_record":
            if user.role!="maintenance":raise HTTPException(403,"仅巡检/维修人员可提交巡检记录")
            task=db.get(InspectionTask,args["task_id"])
            if not task or task.assignee_id!=user.id:raise HTTPException(403,"无权提交该巡检任务")
            operation="inspection_record.submit";idem,replay=claim_idempotency(db,user,operation,idempotency_key,{"task_id":task.id,**args})
            if replay:
                old=db.get(InspectionRecord,idem.resource_id)
                if not old or old.inspector_id!=user.id or old.inspection_task_id!=task.id:raise HTTPException(409,"幂等结果不存在或不属于当前任务")
                return {"inspection_record_id":old.id,"task_no":task.task_no,"status":"submitted","idempotent":True}
            item=InspectionRecord(inspection_task_id=task.id,inspector_id=user.id,description=args["description"],abnormal=args["abnormal"],risk_level=args["risk_level"],idempotency_key=idempotency_storage_key(user.id,operation,idempotency_key));task.status="completed";task.completed_at=utc_now();db.add(item);db.flush()
            rect=None
            if item.abnormal:
                rect=RectificationOrder(rectification_no=number("RO",db,RectificationOrder),inspection_record_id=item.id,description=item.description,risk_level=item.risk_level,deadline=utc_now()+timedelta(days=1 if item.risk_level in {"high","critical"} else 3));db.add(rect);db.flush()
            complete_idempotency(idem,"inspection_record",item.id);audit(db,user,"agent_submit_inspection_record","inspection_task",task.id);db.commit();return {"inspection_record_id":item.id,"task_no":task.task_no,"status":"submitted","rectification_id":rect.id if rect else None,"rectification_no":rect.rectification_no if rect else None,"next_step":"已按异常记录自动生成待整改工单" if rect else "巡检正常，无需整改"}
        if name=="cancel_work_order":
            item=db.get(WorkOrder,args["work_order_id"])
            if not item or item.requester_id!=user.id:raise HTTPException(403,"无权取消该工单")
            result=WorkOrderService().change(db,user,item,"已取消","居民通过智能体取消")
            return {"work_order_id":result.id,"work_order_no":result.work_order_no,"status":result.status}
        if name=="rate_work_order":
            item=db.get(WorkOrder,args["work_order_id"])
            if not item or item.requester_id!=user.id:raise HTTPException(403,"无权评价该工单")
            if item.status!="已完成":raise HTTPException(400,"仅已完成工单可评价")
            old=db.query(WorkOrderRating).filter_by(work_order_id=item.id).first()
            if old:return {"rating_id":old.id,"work_order_no":item.work_order_no,"score":old.score,"idempotent":True}
            row=WorkOrderRating(work_order_id=item.id,resident_id=user.id,score=args["score"],comment=args.get("comment"));db.add(row);audit(db,user,"agent_rate_work_order","work_order",item.id);db.commit();return {"rating_id":row.id,"work_order_no":item.work_order_no,"score":row.score}
        if name=="create_rectification":
            if user.role not in {"customer_service","manager"}:raise HTTPException(403,"无权创建整改工单")
            record=db.get(InspectionRecord,args["inspection_record_id"])
            if not record:raise HTTPException(404,"巡检记录不存在")
            old=db.query(RectificationOrder).filter_by(inspection_record_id=record.id).first()
            if old:return {"rectification_id":old.id,"rectification_no":old.rectification_no,"status":old.status}
            item=RectificationOrder(rectification_no=number("RO",db,RectificationOrder),inspection_record_id=record.id,description=args["description"],risk_level=args["risk_level"],deadline=utc_now()+timedelta(days=3));db.add(item);audit(db,user,"agent_create_rectification","rectification",item.id);db.commit();return {"rectification_id":item.id,"rectification_no":item.rectification_no,"status":item.status}
        if name=="update_rectification_status":
            item=db.get(RectificationOrder,args["rectification_id"])
            if not item or item.assignee_id!=user.id or user.role!="maintenance":raise HTTPException(403,"仅责任维修人员可更新整改状态")
            if args["target_status"] not in {"整改中","待复查"}:raise HTTPException(400,"整改状态不允许")
            if args["target_status"]=="待复查" and not args.get("resolution"):raise HTTPException(400,"提交复查必须填写整改结果")
            item.status=args["target_status"];item.resolution=args.get("resolution") or item.resolution;item.completed_at=utc_now() if item.status=="待复查" else item.completed_at;audit(db,user,"update_rectification_status","rectification",item.id);db.commit();return {"rectification_id":item.id,"status":item.status}
        if name=="review_rectification":
            if user.role!="manager":raise HTTPException(403,"仅经理可人工复查整改")
            item=db.get(RectificationOrder,args["rectification_id"])
            if not item or item.status!="待复查":raise HTTPException(400,"仅待复查整改可审核")
            if args["target_status"] not in {"已关闭","整改中"}:raise HTTPException(400,"复查状态不允许")
            item.status=args["target_status"];item.review_result=args.get("note");item.reviewed_at=utc_now();audit(db,user,"review_rectification","rectification",item.id);db.commit();return {"rectification_id":item.id,"status":item.status}
        raise HTTPException(400,"未注册或禁止的智能体工具")
    return _tool_call(db,run_id,name,args,idempotency_key,work) if run_id else work()

def read_tool(db:Session,user:User,intent:str,fields:dict,text:str,run_id:str|None=None,session_id:str|None=None):
    from harness.service import ExecutionContext
    from mcp_server.gateway import gateway
    result=gateway().execute(db,ExecutionContext(user_id=user.id,role=user.role,source="agent",run_id=run_id,session_id=session_id,request_id=run_id),"agent_read",{"intent":intent,"fields":fields,"text":text})
    if not result.ok: raise HTTPException(400,result.error["message"] if result.error else "查询失败")
    return result.data

def execute(db:Session,user:User,action:dict,idempotency_key:str,run_id:str|None=None,session_id:str|None=None)->dict:
    """Stage 4 entry point.  The LangGraph confirmation node is the trusted proof.

    Business implementations remain in :func:`execute_raw`; no service logic is
    duplicated in the MCP/Harness layer.
    """
    from harness.service import ExecutionContext
    from mcp_server.gateway import gateway
    result=gateway().execute(
        db,
        ExecutionContext(user_id=user.id, role=user.role, source="agent", run_id=run_id, session_id=session_id,
                         confirmed=True, request_id=idempotency_key),
        action.get("action", ""), action, key=idempotency_key,
    )
    if not result.ok: raise HTTPException(503 if result.error and result.error["code"]=="MCP_UNAVAILABLE" else 400,result.error["message"] if result.error else "工具执行失败")
    return result.data
