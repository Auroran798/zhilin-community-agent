import uuid
import re
from fastapi import FastAPI, Depends, Header, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, Binding, Property, WorkOrder, WorkOrderEvent, WorkOrderRating, Announcement, Bill, PaymentRecord, BillReviewRequest, InspectionTask, InspectionRecord, RectificationOrder, AuditLog, KnowledgeDocument, KnowledgeSource, KnowledgeChunk, KnowledgeIngestionJob, RagFeedback, RagQueryLog, Notification, InspectionPlan, Equipment
from .schemas import LoginIn, WorkOrderIn, AssignIn, TransitionIn, RatingIn, AnnouncementIn, ReviewIn, HandleReviewIn, InspectionTaskIn, InspectionRecordIn, RectificationIn, ApprovalIn, InspectionPlanIn, EquipmentIn
from agent.schemas import AgentMessageIn, ConfirmationIn, ConfirmationModifyIn, MemoryIn, ResumeIn, ReviewAssignIn, ReviewResolveIn
from agent.service import AgentService
from .security import verify_password, create_token, current_user, require_roles
from .services import WorkOrderService, DashboardService, audit, number, bound_property
from .config import settings
from rag.service import ALLOWED, VectorStore, create_job, digest, ingest, quality_profile, search, validate_upload
from pathlib import Path
from .observability import router as observability_router, mcp_router as mcp_observability_router
from .integrations import router as property_system_integration_router
from .public_real import router as public_real_router
from .stage7 import AnnouncementService, AssignmentService, BillingService, EquipmentService, InspectionService, SchedulerService, SLAService, notify
from .idempotency import claim as claim_idempotency, complete as complete_idempotency, storage_key as idempotency_storage_key
from .time import utc_now

app=FastAPI(title="智邻管家：物业社区管理智能体 API",version="1.3.0")
app.include_router(observability_router)
app.include_router(mcp_observability_router)
app.include_router(property_system_integration_router)
app.include_router(public_real_router)

# Defense in depth around HTTP targets and request size.  Starlette itself is
# pinned to a patched release; these checks keep malformed traffic out of the
# application and cap form parsing work at the edge.
_HOST = re.compile(r"^(?:localhost|testserver|[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?)(?::\d{1,5})?$")
@app.middleware("http")
async def reject_malformed_http_target(request: Request, call_next):
    host = request.headers.get("host", "")
    raw_path = request.scope.get("raw_path", b"")
    content_length = request.headers.get("content-length")
    if not _HOST.fullmatch(host) or not raw_path.startswith(b"/"):
        return JSONResponse(status_code=400, content={"success": False, "error": {"code": "INVALID_HTTP_TARGET", "message": "Malformed Host or request target", "details": {}}, "request_id": str(uuid.uuid4())})
    try:
        declared_size = int(content_length) if content_length else 0
    except ValueError:
        return JSONResponse(status_code=400, content={"success": False, "error": {"code": "INVALID_CONTENT_LENGTH", "message": "Content-Length must be numeric", "details": {}}, "request_id": str(uuid.uuid4())})
    if declared_size > settings.max_request_body_size_mb * 1024 * 1024:
        return JSONResponse(status_code=413, content={"success": False, "error": {"code": "REQUEST_TOO_LARGE", "message": "Request body exceeds limit", "details": {}}, "request_id": str(uuid.uuid4())})
    if not content_length and request.method in {"POST","PUT","PATCH"}:
        limit=settings.max_request_body_size_mb*1024*1024; buffered=bytearray()
        async for chunk in request.stream():
            buffered.extend(chunk)
            if len(buffered)>limit:
                return JSONResponse(status_code=413,content={"success":False,"error":{"code":"REQUEST_TOO_LARGE","message":"Chunked request body exceeds limit","details":{}},"request_id":str(uuid.uuid4())})
        delivered=False
        async def replay_body():
            nonlocal delivered
            if delivered:return {"type":"http.request","body":b"","more_body":False}
            delivered=True;return {"type":"http.request","body":bytes(buffered),"more_body":False}
        request._receive=replay_body
    return await call_next(request)
def row(x): return {c.name:getattr(x,c.name) for c in x.__table__.columns}
def ok(data,message="操作成功"): return {"success":True,"data":data,"message":message,"request_id":str(uuid.uuid4())}

def _require_governed_official_source(db:Session,doc:KnowledgeDocument)->KnowledgeSource:
    source=db.get(KnowledgeSource,doc.source_id) if doc.source_id else None
    if not source: raise HTTPException(400,"Official documents must originate from the governed source registry")
    if not (source.actually_downloaded and source.manually_verified and source.answerable and source.review_status=="approved"):
        raise HTTPException(400,"Official source is pending or failed download/review governance")
    if source.file_hash!=doc.file_hash or source.source_url!=doc.source_url:
        raise HTTPException(400,"Official document no longer matches its governed source checksum or URL")
    return source

@app.exception_handler(HTTPException)
async def http_error(request,exc): return JSONResponse(status_code=exc.status_code,content={"success":False,"error":{"code":"PERMISSION_DENIED" if exc.status_code==403 else "BUSINESS_ERROR","message":str(exc.detail),"details":{}},"request_id":str(uuid.uuid4())})
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/ready")
def ready(db:Session=Depends(get_db)):
 db.execute(__import__("sqlalchemy").text("SELECT 1"))
 store=VectorStore()
 if not store.ready: raise HTTPException(503,"Chroma vector store is unavailable")
 profile=quality_profile()
 return {"status":"ready","database":"ok","vector_store":"ok","embedding_model":store.embedding.model_name,"rag_quality":profile}

def agent_row(x): return {c.name:getattr(x,c.name) for c in x.__table__.columns}
@app.post("/api/v1/agent/sessions")
def create_agent_session(user:User=Depends(current_user),db:Session=Depends(get_db)): return ok(agent_row(AgentService().create_session(db,user)))
@app.get("/api/v1/agent/sessions")
def list_agent_sessions(user:User=Depends(current_user),db:Session=Depends(get_db)): return ok([agent_row(x) for x in AgentService().sessions(db,user)])
@app.get("/api/v1/agent/sessions/{session_id}")
def get_agent_session(session_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 return ok(agent_row(AgentService().owned_session(db,user,session_id)))
@app.get("/api/v1/agent/sessions/{session_id}/messages")
def get_agent_messages(session_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 return ok([agent_row(x) for x in AgentService().messages(db,user,session_id)])
@app.post("/api/v1/agent/sessions/{session_id}/messages")
def send_agent_message(session_id:str,data:AgentMessageIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
 return ok(AgentService().turn(db,user,session_id,data.content,data.product_mode,data.jurisdiction))
@app.post("/api/v1/agent/confirmations/{confirmation_id}")
def confirm_agent_action(confirmation_id:str,data:ConfirmationIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
 return ok(AgentService().confirm(db,user,confirmation_id) if data.decision=="confirm" else AgentService().cancel_confirmation(db,user,confirmation_id))
@app.post("/api/v1/agent/sessions/{session_id}/resume")
def resume_agent_session(session_id:str,data:ResumeIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
 service=AgentService();service.owned_session(db,user,session_id)
 return ok(service.turn(db,user,session_id,data.message) if data.message else service.state(db,user,session_id))
@app.post("/api/v1/agent/sessions/{session_id}/cancel")
def cancel_agent_session(session_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)): return ok(agent_row(AgentService().cancel_session(db,user,session_id)))
@app.get("/api/v1/agent/sessions/{session_id}/state")
def agent_session_state(session_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)): return ok(AgentService().state(db,user,session_id))
@app.get("/api/v1/agent/confirmations/{confirmation_id}")
def get_agent_confirmation(confirmation_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)): return ok(agent_row(AgentService().confirmation(db,user,confirmation_id)))
@app.post("/api/v1/agent/confirmations/{confirmation_id}/confirm")
def confirm_agent_confirmation(confirmation_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)): return ok(AgentService().confirm(db,user,confirmation_id))
@app.post("/api/v1/agent/confirmations/{confirmation_id}/modify")
def modify_agent_confirmation(confirmation_id:str,data:ConfirmationModifyIn,user:User=Depends(current_user),db:Session=Depends(get_db)): return ok(AgentService().modify_confirmation(db,user,confirmation_id,data.fields))
@app.post("/api/v1/agent/confirmations/{confirmation_id}/cancel")
def cancel_agent_confirmation(confirmation_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)): return ok(AgentService().cancel_confirmation(db,user,confirmation_id))
@app.get("/api/v1/agent/memories")
def get_agent_memories(user:User=Depends(current_user),db:Session=Depends(get_db)):
 from api.models import AgentMemory
 return ok([agent_row(x) for x in db.query(AgentMemory).filter_by(user_id=user.id).filter(AgentMemory.deleted_at.is_(None)).all()])
@app.put("/api/v1/agent/memories")
def put_agent_memory(data:MemoryIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
 return ok(agent_row(AgentService().save_memory(db,user,data.memory_key,data.value,data.memory_type,data.consented)))
@app.delete("/api/v1/agent/memories/{memory_key}")
def delete_agent_memory(memory_key:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 AgentService().delete_memory(db,user,memory_key);return ok({"deleted":memory_key})
@app.get("/api/v1/agent/human-reviews")
def list_agent_reviews(user:User=Depends(current_user),db:Session=Depends(get_db)): return ok([agent_row(x) for x in AgentService().reviews(db,user)])
@app.get("/api/v1/agent/human-reviews/{review_id}")
def get_agent_review(review_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)): return ok(agent_row(AgentService().review(db,user,review_id)))
@app.post("/api/v1/agent/human-reviews/{review_id}/assign")
def assign_agent_review(review_id:str,data:ReviewAssignIn,user:User=Depends(current_user),db:Session=Depends(get_db)): return ok(agent_row(AgentService().assign_review(db,user,review_id,data.assignee_id)))
@app.post("/api/v1/agent/human-reviews/{review_id}/resolve")
def resolve_agent_review(review_id:str,data:ReviewResolveIn,user:User=Depends(current_user),db:Session=Depends(get_db)): return ok(agent_row(AgentService().resolve_review(db,user,review_id,data.result)))

@app.post("/api/v1/auth/login")
def login(data:LoginIn,db:Session=Depends(get_db)):
 u=db.query(User).filter_by(username=data.username).first()
 if not u or not u.is_active or not verify_password(data.password,u.password_hash):
  audit(db,u,"login","auth",getattr(u,"id",None),"denied","用户名或密码错误");db.commit();raise HTTPException(401,"用户名或密码错误")
 audit(db,u,"login","auth",u.id);db.commit();return ok({"access_token":create_token(u),"token_type":"bearer","user":row(u)})
@app.get("/api/v1/auth/me")
@app.get("/api/v1/users/me")
def me(user:User=Depends(current_user)): return ok(row(user))
@app.get("/api/v1/properties/my")
def my_properties(user:User=Depends(current_user),db:Session=Depends(get_db)):
 ids=[x.property_id for x in db.query(Binding).filter_by(user_id=user.id)]
 q=db.query(Property) if user.role!="resident" else db.query(Property).filter(Property.id.in_(ids))
 return ok([row(x) for x in q.all()])

def get_order(db,user,id):
 o=db.get(WorkOrder,id)
 if not o: raise HTTPException(404,"工单不存在")
 if user.role=="resident" and o.requester_id!=user.id: audit(db,user,"view_work_order","work_order",id,"denied","非本人");db.commit();raise HTTPException(403,"无权查看该工单")
 if user.role=="maintenance" and o.assignee_id!=user.id: raise HTTPException(403,"无权查看该工单")
 return o
@app.post("/api/v1/work-orders")
def create_work_order(data:WorkOrderIn,idempotency_key:str|None=Header(None,alias="Idempotency-Key"),user:User=Depends(require_roles("resident")),db:Session=Depends(get_db)): return ok(row(WorkOrderService().create(db,user,data,idempotency_key)))
@app.get("/api/v1/work-orders")
def list_work_orders(status:str|None=None,user:User=Depends(current_user),db:Session=Depends(get_db)):
 q=db.query(WorkOrder)
 if user.role=="resident":q=q.filter_by(requester_id=user.id)
 if user.role=="maintenance":q=q.filter_by(assignee_id=user.id)
 if status:q=q.filter_by(status=status)
 return ok([row(x) for x in q.order_by(WorkOrder.created_at.desc()).all()])
@app.get("/api/v1/work-orders/{order_id}")
def detail(order_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)): return ok(row(get_order(db,user,order_id)))
@app.post("/api/v1/work-orders/{order_id}/cancel")
def cancel(order_id:str,user:User=Depends(require_roles("resident","customer_service","manager")),db:Session=Depends(get_db)):
 return ok(row(WorkOrderService().change(db,user,get_order(db,user,order_id),"已取消","用户取消")))
@app.post("/api/v1/work-orders/{order_id}/accept")
def accept(order_id:str,user:User=Depends(require_roles("customer_service","manager")),db:Session=Depends(get_db)): return ok(row(WorkOrderService().change(db,user,get_order(db,user,order_id),"已受理","客服受理")))
@app.post("/api/v1/work-orders/{order_id}/assign")
def assign(order_id:str,data:AssignIn,user:User=Depends(require_roles("customer_service","manager")),db:Session=Depends(get_db)):
 o=get_order(db,user,order_id)
 return ok(row(AssignmentService.assign(db,user,o,data.assignee_id,data.note)))
@app.get("/api/v1/work-orders/{order_id}/sla")
def work_order_sla(order_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 o=get_order(db,user,order_id); return ok(SLAService.get_status(o))
@app.get("/api/v1/work-orders/{order_id}/assignee-recommendation")
def recommend_assignee(order_id:str,user:User=Depends(require_roles("customer_service","manager")),db:Session=Depends(get_db)):
 return ok(AssignmentService.recommend(db,get_order(db,user,order_id)))
@app.post("/api/v1/work-orders/{order_id}/transition")
def change(order_id:str,data:TransitionIn,user:User=Depends(current_user),db:Session=Depends(get_db)): return ok(row(WorkOrderService().change(db,user,get_order(db,user,order_id),data.target_status,data.note,data.resolution)))
@app.get("/api/v1/work-orders/{order_id}/timeline")
def timeline(order_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)): get_order(db,user,order_id);return ok([row(x) for x in db.query(WorkOrderEvent).filter_by(work_order_id=order_id).all()])
@app.post("/api/v1/work-orders/{order_id}/rating")
def rating(order_id:str,data:RatingIn,user:User=Depends(require_roles("resident")),db:Session=Depends(get_db)):
 o=get_order(db,user,order_id)
 if o.status not in {"已完成","已关闭"}:raise HTTPException(400,"仅完成后的工单可评价")
 if db.query(WorkOrderRating).filter_by(work_order_id=o.id).first():raise HTTPException(409,"工单已评价")
 r=WorkOrderRating(work_order_id=o.id,resident_id=user.id,**data.model_dump());db.add(r);audit(db,user,"rate_work_order","work_order",o.id);db.commit();return ok(row(r))

@app.get("/api/v1/announcements")
def announcements(user:User=Depends(current_user),db:Session=Depends(get_db)):
 q=db.query(Announcement)
 if user.role=="resident":
  q=q.filter_by(status="published")
  binding_ids=[x.property_id for x in db.query(Binding).filter_by(user_id=user.id)]
  buildings={x.building_no for x in db.query(Property).filter(Property.id.in_(binding_ids))}
  q=q.filter((Announcement.target_type!="building") | (Announcement.target_building_no.in_(buildings)))
 return ok([row(x) for x in q.all()])
@app.post("/api/v1/announcements")
def create_announcement(data:AnnouncementIn,user:User=Depends(require_roles("customer_service","manager")),db:Session=Depends(get_db)):
 a=Announcement(**data.model_dump(),created_by=user.id);db.add(a);db.commit();return ok(row(a))
@app.post("/api/v1/announcements/{id}/submit-review")
def submit(id:str,user:User=Depends(require_roles("customer_service","manager")),db:Session=Depends(get_db)):
 a=db.get(Announcement,id)
 if not a or (a.created_by!=user.id and user.role!="manager"):raise HTTPException(403,"无权提交该公告审核")
 return ok(row(AnnouncementService.submit(db,user,a)))
@app.post("/api/v1/announcements/{id}/approve")
def approve(id:str,data:ApprovalIn|None=None,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 a=db.get(Announcement,id)
 if not a:raise HTTPException(404,"公告不存在")
 data=data or ApprovalIn()
 return ok(row(AnnouncementService.approve(db,user,a,data.decision,data.review_comment)))
@app.post("/api/v1/announcements/{id}/reject")
def reject(id:str,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 a=db.get(Announcement,id)
 if not a:raise HTTPException(404,"公告不存在")
 return ok(row(AnnouncementService.approve(db,user,a,"rejected")))
@app.post("/api/v1/announcements/{id}/publish")
def publish(id:str,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 a=db.get(Announcement,id)
 if not a:raise HTTPException(404,"公告不存在")
 a=AnnouncementService.publish(db,user,a)
 return ok(row(a),"公告已发布，知识索引将由后台任务同步")
@app.post("/api/v1/announcements/{id}/withdraw")
def withdraw_announcement(id:str,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 a=db.get(Announcement,id)
 if not a:raise HTTPException(404,"公告不存在")
 return ok(row(AnnouncementService.withdraw(db,user,a)),"公告已撤回，知识索引将由后台任务同步")

@app.get("/api/v1/bills")
def bills(user:User=Depends(current_user),db:Session=Depends(get_db)):
 q=db.query(Bill)
 if user.role=="resident":q=q.filter(Bill.property_id.in_([x.property_id for x in db.query(Binding).filter_by(user_id=user.id)]))
 return ok([row(x) for x in q.all()])
@app.get("/api/v1/bills/{id}/payments")
def payments(id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 b=db.get(Bill,id)
 if not b:raise HTTPException(404,"账单不存在")
 bound_property(db,user,b.property_id);return ok([row(x) for x in db.query(PaymentRecord).filter_by(bill_id=id)])
@app.get("/api/v1/bills/{id}")
def bill_detail(id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 b=db.get(Bill,id)
 if not b: raise HTTPException(404,"账单不存在")
 bound_property(db,user,b.property_id);audit(db,user,"view_bill","bill",id);db.commit();return ok(row(b))
@app.get("/api/v1/bills/{id}/details")
def bill_details(id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 data=BillingService.details(db,user,id)
 return ok({"bill":row(data["bill"]),"items":[row(x) for x in data["items"]],"paid_amount":str(data["paid_amount"]),"balance":str(data["balance"])})
@app.get("/api/v1/bills/{id}/compare/{previous_id}")
def compare_bill(id:str,previous_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 return ok(BillingService.compare(db,user,id,previous_id))
@app.get("/api/v1/bills/{id}/payment-history")
def bill_payment_history(id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 bill=db.get(Bill,id)
 if not bill:raise HTTPException(404,"账单不存在")
 return ok([row(x) for x in BillingService.payment_history(db,user,bill.property_id)])
@app.post("/api/v1/bills/{id}/review-requests")
def review(id:str,data:ReviewIn,idempotency_key:str|None=Header(None,alias="Idempotency-Key"),user:User=Depends(require_roles("resident")),db:Session=Depends(get_db)):
 b=db.get(Bill,id)
 if not b:raise HTTPException(404,"账单不存在")
 BillingService.assert_visible(db,user,b)
 operation="bill_review.create";idem,replay=claim_idempotency(db,user,operation,idempotency_key,{"bill_id":id,**data.model_dump(mode="json")})
 if replay:
  x=db.get(BillReviewRequest,idem.resource_id)
  if not x or x.resident_id!=user.id:raise HTTPException(409,"幂等结果不存在或不属于当前用户")
  return ok(row(x))
 x=BillReviewRequest(request_no=number("BR",db,BillReviewRequest),bill_id=id,resident_id=user.id,reason=data.reason,status="submitted",idempotency_key=idempotency_storage_key(user.id,operation,idempotency_key) if idempotency_key else None);db.add(x);db.flush();complete_idempotency(idem,"bill_review",x.id,{"request_no":x.request_no});audit(db,user,"create_bill_review","bill_review",x.id);db.commit();return ok(row(x))
@app.get("/api/v1/bill-review-requests")
def review_requests(user:User=Depends(current_user),db:Session=Depends(get_db)):
 q=db.query(BillReviewRequest)
 if user.role=="resident": q=q.filter_by(resident_id=user.id)
 if user.role=="maintenance": raise HTTPException(403,"维修人员无权查看费用核查")
 return ok([row(x) for x in q.all()])
@app.get("/api/v1/bill-review-requests/{request_id}")
def review_detail(request_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 x=db.get(BillReviewRequest,request_id)
 if not x: raise HTTPException(404,"核查申请不存在")
 if user.role=="resident" and x.resident_id!=user.id: raise HTTPException(403,"无权查看该核查申请")
 if user.role=="maintenance": raise HTTPException(403,"无权查看费用核查")
 return ok(row(x))
@app.post("/api/v1/bill-review-requests/{request_id}/handle")
def handle_review(request_id:str,data:HandleReviewIn,user:User=Depends(require_roles("customer_service","manager")),db:Session=Depends(get_db)):
 x=db.get(BillReviewRequest,request_id)
 if not x: raise HTTPException(404,"核查申请不存在")
 x.status="resolved";x.handler_id=user.id;x.result=data.result;x.handled_at=utc_now();notify(db,x.resident_id,"BILL_REVIEW_RESULT","费用复核结果已出具",data.result,"bill_review",x.id);audit(db,user,"handle_bill_review","bill_review",x.id);db.commit();return ok(row(x))

@app.post("/api/v1/inspection-tasks")
def task(data:InspectionTaskIn,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 t=InspectionTask(task_no=number("IT",db,InspectionTask),created_by=user.id,**data.model_dump());db.add(t);db.commit();return ok(row(t))
@app.post("/api/v1/inspection-plans")
def create_inspection_plan(data:InspectionPlanIn,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 if data.frequency not in {"daily","weekly","monthly"}:raise HTTPException(400,"frequency 仅支持 daily、weekly 或 monthly")
 if data.assignee_id:
  assignee=db.get(User,data.assignee_id)
  if not assignee or assignee.role!="maintenance":raise HTTPException(400,"巡检人必须是维修/巡检人员")
 plan=InspectionPlan(created_by=user.id,assigned_role="maintenance",**data.model_dump());db.add(plan);audit(db,user,"create_inspection_plan","inspection_plan",plan.id);db.commit();return ok(row(plan))
@app.get("/api/v1/inspection-plans")
def list_inspection_plans(user:User=Depends(require_roles("customer_service","maintenance","manager")),db:Session=Depends(get_db)):
 return ok([row(x) for x in db.query(InspectionPlan).order_by(InspectionPlan.next_run_at).all()])
@app.get("/api/v1/inspection-tasks")
def tasks(user:User=Depends(current_user),db:Session=Depends(get_db)):
 q=db.query(InspectionTask);q=q.filter_by(assignee_id=user.id) if user.role=="maintenance" else q;return ok([row(x) for x in q.all()])
@app.get("/api/v1/inspection-tasks/{task_id}")
def task_detail(task_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 t=db.get(InspectionTask,task_id)
 if not t: raise HTTPException(404,"巡检任务不存在")
 if user.role=="maintenance" and t.assignee_id!=user.id: raise HTTPException(403,"无权查看该巡检任务")
 return ok(row(t))
@app.post("/api/v1/inspection-tasks/{task_id}/records")
def submit_record(task_id:str,data:InspectionRecordIn,idempotency_key:str|None=Header(None,alias="Idempotency-Key"),user:User=Depends(require_roles("maintenance")),db:Session=Depends(get_db)):
 t=db.get(InspectionTask,task_id)
 if not t or t.assignee_id!=user.id: audit(db,user,"submit_inspection_record","inspection_task",task_id,"denied","未分配任务");db.commit();raise HTTPException(403,"无权提交该巡检记录")
 operation="inspection_record.submit";idem,replay=claim_idempotency(db,user,operation,idempotency_key,{"task_id":task_id,**data.model_dump(mode="json")})
 if replay:
  old=db.get(InspectionRecord,idem.resource_id)
  if not old or old.inspector_id!=user.id or old.inspection_task_id!=task_id:raise HTTPException(409,"幂等结果不存在或不属于当前任务")
  return ok(row(old))
 record=InspectionRecord(inspection_task_id=t.id,inspector_id=user.id,idempotency_key=idempotency_storage_key(user.id,operation,idempotency_key) if idempotency_key else None,**data.model_dump())
 t.status="completed";t.completed_at=utc_now();db.add(record);db.flush()
 if record.abnormal:
  notify(db,t.created_by,"RECTIFICATION_CREATED","巡检发现异常",f"巡检任务 {t.task_no} 已发现 {record.risk_level} 风险，请创建整改工单。","inspection_record",record.id)
 complete_idempotency(idem,"inspection_record",record.id);audit(db,user,"submit_inspection_record","inspection_task",t.id);db.commit();return ok(row(record))
@app.post("/api/v1/rectification-orders")
def create_rectification(data:RectificationIn,idempotency_key:str|None=Header(None,alias="Idempotency-Key"),user:User=Depends(require_roles("customer_service","manager")),db:Session=Depends(get_db)):
 record=db.get(InspectionRecord,data.inspection_record_id)
 if not record: raise HTTPException(404,"巡检记录不存在")
 operation="rectification.create";idem,replay=claim_idempotency(db,user,operation,idempotency_key,data.model_dump(mode="json"))
 if replay:
  old=db.get(RectificationOrder,idem.resource_id)
  if not old:raise HTTPException(409,"幂等结果不存在")
  return ok(row(old))
 if db.query(RectificationOrder).filter_by(inspection_record_id=record.id).first(): raise HTTPException(409,"该异常已创建整改工单")
 rect=InspectionService.create_rectification(db,user,record,data.deadline,data.equipment_id)
 if rect.assignee_id:notify(db,rect.assignee_id,"RECTIFICATION_CREATED","您有新的整改任务",f"整改工单 {rect.rectification_no} 已创建。","rectification",rect.id)
 complete_idempotency(idem,"rectification",rect.id);db.commit();return ok(row(rect))
@app.get("/api/v1/rectification-orders")
def list_rectifications(user:User=Depends(current_user),db:Session=Depends(get_db)):
 q=db.query(RectificationOrder)
 if user.role=="maintenance": q=q.filter_by(assignee_id=user.id)
 elif user.role=="resident": raise HTTPException(403,"居民无权查看整改任务")
 return ok([row(x) for x in q.all()])
@app.get("/api/v1/rectification-orders/{rectification_id}")
def rectification_detail(rectification_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 r=db.get(RectificationOrder,rectification_id)
 if not r: raise HTTPException(404,"整改工单不存在")
 if user.role=="maintenance" and r.assignee_id!=user.id: raise HTTPException(403,"无权查看该整改工单")
 if user.role=="resident": raise HTTPException(403,"居民无权查看整改任务")
 return ok(row(r))
@app.post("/api/v1/rectification-orders/{rectification_id}/assign")
def assign_rectification(rectification_id:str,data:AssignIn,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 r=db.get(RectificationOrder,rectification_id); worker=db.get(User,data.assignee_id)
 if not r: raise HTTPException(404,"整改工单不存在")
 if not worker or worker.role!="maintenance": raise HTTPException(400,"处理人必须是维修或巡检人员")
 r.assignee_id=worker.id;r.status="整改中";notify(db,worker.id,"RECTIFICATION_CREATED","您有新的整改任务",f"整改工单 {r.rectification_no} 已派给您。","rectification",r.id);audit(db,user,"assign_rectification","rectification",r.id);db.commit();return ok(row(r))
@app.post("/api/v1/rectification-orders/{rectification_id}/complete")
def complete_rectification(rectification_id:str,data:TransitionIn,user:User=Depends(require_roles("maintenance")),db:Session=Depends(get_db)):
 r=db.get(RectificationOrder,rectification_id)
 if not r or r.assignee_id!=user.id: raise HTTPException(403,"无权处理该整改工单")
 if r.status not in {"待整改","整改中"}: raise HTTPException(400,"当前状态不可提交整改结果")
 if not data.resolution: raise HTTPException(400,"必须填写整改结果")
 r.resolution=data.resolution;r.status="待复查";r.completed_at=utc_now();audit(db,user,"complete_rectification","rectification",r.id);db.commit();return ok(row(r))
@app.post("/api/v1/rectification-orders/{rectification_id}/review")
def review_rectification(rectification_id:str,data:TransitionIn,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 r=db.get(RectificationOrder,rectification_id)
 if not r or r.status!="待复查": raise HTTPException(400,"仅待复查整改工单可复查")
 if data.target_status not in {"已关闭","整改中"}: raise HTTPException(400,"复查结果必须为已关闭或整改中")
 r.status=data.target_status;r.review_result=data.note;r.reviewed_at=utc_now();
 if r.status=="已关闭" and r.assignee_id:notify(db,r.assignee_id,"RECTIFICATION_COMPLETED","整改复查已关闭",f"整改工单 {r.rectification_no} 已经人工复查关闭。","rectification",r.id)
 audit(db,user,"review_rectification","rectification",r.id);db.commit();return ok(row(r))
@app.get("/api/v1/dashboard/summary")
def dashboard(user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)): return ok(DashboardService().summary(db))
@app.post("/api/v1/scheduler/run-due")
def run_due_scheduler(user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 return ok(SchedulerService.run_due(db,user))
@app.get("/api/v1/notifications")
def list_notifications(unread_only:bool=False,user:User=Depends(current_user),db:Session=Depends(get_db)):
 q=db.query(Notification).filter_by(recipient_user_id=user.id)
 if unread_only:q=q.filter_by(status="unread")
 items=q.order_by(Notification.created_at.desc()).limit(200).all()
 return ok({"unread_count":db.query(Notification).filter_by(recipient_user_id=user.id,status="unread").count(),"items":[row(x) for x in items]})
@app.post("/api/v1/notifications/{notification_id}/read")
def read_notification(notification_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
 item=db.get(Notification,notification_id)
 if not item or item.recipient_user_id!=user.id:raise HTTPException(404,"通知不存在")
 if item.status=="unread":item.status="read";item.read_at=utc_now();db.commit()
 return ok(row(item))
@app.post("/api/v1/equipment")
def create_equipment(data:EquipmentIn,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 if db.query(Equipment).filter_by(equipment_code=data.equipment_code).first():raise HTTPException(409,"设备编码已存在")
 if data.property_id and not db.get(Property,data.property_id):raise HTTPException(400,"房屋不存在")
 item=Equipment(**data.model_dump());db.add(item);audit(db,user,"create_equipment","equipment",item.id);db.commit();return ok(row(item))
@app.get("/api/v1/equipment")
def search_equipment(q:str|None=None,category:str|None=None,status:str|None=None,building_no:str|None=None,user:User=Depends(require_roles("customer_service","maintenance","manager")),db:Session=Depends(get_db)):
 query=db.query(Equipment)
 if q:query=query.filter((Equipment.name.contains(q))|(Equipment.equipment_code.contains(q))|(Equipment.location.contains(q)))
 if category:query=query.filter_by(category=category)
 if status:query=query.filter_by(status=status)
 if building_no:query=query.join(Property,Equipment.property_id==Property.id).filter(Property.building_no==building_no)
 return ok([row(x) for x in query.order_by(Equipment.created_at.desc()).all()])
@app.get("/api/v1/equipment/{equipment_id}")
def get_equipment(equipment_id:str,user:User=Depends(require_roles("customer_service","maintenance","manager")),db:Session=Depends(get_db)):
 item=db.get(Equipment,equipment_id)
 if not item:raise HTTPException(404,"设备不存在")
 return ok(row(item))
@app.get("/api/v1/equipment/{equipment_id}/history")
def equipment_history(equipment_id:str,user:User=Depends(require_roles("customer_service","maintenance","manager")),db:Session=Depends(get_db)):
 data=EquipmentService.history(db,equipment_id)
 return ok({key:(row(value) if key=="equipment" else [row(x) for x in value]) for key,value in data.items()})
@app.get("/api/v1/audit-logs")
def logs(user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)): return ok([row(x) for x in db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)])

@app.post("/api/v1/knowledge/documents")
async def upload_knowledge_document(file:UploadFile=File(...), title:str=Form(...), document_type:str=Form("community_rule"), source_type:str=Form("synthetic_community_document"), applicable_community:str|None=Form(None), version:str=Form("1.0"), source_url:str|None=Form(None), publisher:str|None=Form(None), country:str|None=Form(None), jurisdiction:str|None=Form(None), language:str=Form("zh-CN"), answerable:bool=Form(True), authority_level:str=Form("community"), authority_status:str|None=Form(None), license_note:str|None=Form(None), license_url:str|None=Form(None), contains_personal_data:bool=Form(False), minimization_rule:str|None=Form(None), user:User=Depends(require_roles("manager")), db:Session=Depends(get_db)):
    suffix=Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED: raise HTTPException(400,"Unsupported knowledge file type")
    payload=await file.read()
    if not payload or len(payload)>settings.max_knowledge_file_size_mb*1024*1024: raise HTTPException(400,"Invalid or oversized knowledge file")
    try: validate_upload(suffix,file.content_type,payload)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    file_hash=digest(payload)
    if old:=db.query(KnowledgeDocument).filter_by(file_hash=file_hash).first(): return ok(row(old),"Duplicate file reused")
    if source_type not in {"official_public_document","synthetic_community_document","stage1_published_announcement"}: raise HTTPException(400,"Invalid knowledge source type")
    if source_type=="official_public_document":
        missing=[name for name,value in (("source_url",source_url),("publisher",publisher),("country",country),("jurisdiction",jurisdiction),("language",language),("authority_level",authority_level),("license_note",license_note),("license_url",license_url)) if not value]
        if missing: raise HTTPException(400,"Official documents require governed metadata: "+", ".join(missing))
        if not source_url.startswith("https://") or not license_url.startswith("https://"): raise HTTPException(400,"Official source and license URLs must use HTTPS")
        if contains_personal_data and not minimization_rule: raise HTTPException(400,"Sources containing personal data require a minimization rule")
    root=Path(settings.rag_storage_path); root.mkdir(parents=True,exist_ok=True); stored=root/f"{file_hash}{suffix}"; stored.write_bytes(payload)
    data_class="KB_POLICY" if source_type=="official_public_document" else "DEMO_SYNTHETIC"
    governed_jurisdiction=jurisdiction or (applicable_community if source_type=="synthetic_community_document" else None)
    doc=KnowledgeDocument(document_no=number("KD",db,KnowledgeDocument),title=title,document_type=document_type,source_type=source_type,data_class=data_class,source_url=source_url,publisher=publisher,country=country,jurisdiction=governed_jurisdiction,language=language,answerable=answerable,authority_level=authority_level,authority_status=authority_status,license_note=license_note,license_url=license_url,contains_personal_data=contains_personal_data,minimization_rule=minimization_rule,review_status="approved" if source_type=="synthetic_community_document" else "pending",applicable_community=applicable_community,version=version,file_name=Path(file.filename or "upload").name,file_type=suffix.lstrip("."),file_size=len(payload),file_hash=file_hash,storage_path=str(stored),created_by=user.id,is_authoritative=source_type=="official_public_document",is_synthetic=source_type=="synthetic_community_document",status="uploaded")
    db.add(doc); audit(db,user,"upload_knowledge_document","knowledge_document",doc.id); db.commit(); db.refresh(doc); return ok(row(doc))

@app.post("/api/v1/knowledge/documents/{document_id}/index")
def index_knowledge_document(document_id:str,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
    doc=db.get(KnowledgeDocument,document_id)
    if not doc: raise HTTPException(404,"Knowledge document not found")
    job=create_job(db,doc,user.id)
    try: total=ingest(db,doc,job)
    except Exception as exc:
        doc.status="failed";db.commit();raise HTTPException(400,f"Indexing failed: {exc}")
    audit(db,user,"index_knowledge_document","knowledge_document",doc.id);db.commit();return ok({"document":row(doc),"job":row(job),"result":total})

@app.post("/api/v1/knowledge/documents/{document_id}/versions")
async def update_knowledge_document(document_id:str,file:UploadFile=File(...),version:str=Form(...),change_summary:str=Form("content update"),user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
    """Replace a controlled document's current content and immediately re-index it.

    The previous version row remains immutable; visibility still follows the
    review/activation state rather than silently exposing an unreviewed update.
    """
    doc=db.get(KnowledgeDocument,document_id)
    if not doc: raise HTTPException(404,"Knowledge document not found")
    suffix=Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED: raise HTTPException(400,"Unsupported knowledge file type")
    payload=await file.read(); file_hash=digest(payload)
    if not payload or len(payload)>settings.max_knowledge_file_size_mb*1024*1024: raise HTTPException(400,"Invalid or oversized knowledge file")
    try: validate_upload(suffix,file.content_type,payload)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    if version==doc.version: raise HTTPException(400,"Version must change for a content update")
    previous={name:getattr(doc,name) for name in (
        "file_name","file_type","file_size","file_hash","storage_path","version","status",
        "content_hash","raw_text","cleaned_text","indexed_at",
    )}
    root=Path(settings.rag_storage_path);root.mkdir(parents=True,exist_ok=True);stored=root/f"{file_hash}{suffix}";stored.write_bytes(payload)
    doc.file_name=Path(file.filename or "update").name;doc.file_type=suffix.lstrip(".");doc.file_size=len(payload);doc.file_hash=file_hash;doc.storage_path=str(stored);doc.version=version;doc.status="uploaded"
    job=create_job(db,doc,user.id)
    try: result=ingest(db,doc,job)
    except Exception as exc:
        # create_job commits the new metadata before indexing. Restore the
        # previous current-version pointer when parsing/vector persistence fails.
        doc=db.get(KnowledgeDocument,document_id)
        for name,value in previous.items(): setattr(doc,name,value)
        db.commit()
        raise HTTPException(400,f"Indexing failed: {exc}") from exc
    from .models import KnowledgeDocumentVersion
    record=db.query(KnowledgeDocumentVersion).filter_by(document_id=doc.id,version=version).first()
    if record: record.change_summary=change_summary[:1000]
    audit(db,user,"update_knowledge_document","knowledge_document",doc.id,"success",change_summary[:1000]);db.commit()
    return ok({"document":row(doc),"job":row(job),"result":result})

@app.post("/api/v1/knowledge/documents/{document_id}/activate")
def activate_knowledge_document(document_id:str,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
    doc=db.get(KnowledgeDocument,document_id)
    if not doc: raise HTTPException(404,"Knowledge document not found")
    if doc.status!="indexed": raise HTTPException(400,"Document must be indexed before activation")
    if doc.source_type=="official_public_document":
        _require_governed_official_source(db,doc)
        if doc.review_status!="approved": raise HTTPException(400,"Official document must pass review before activation")
    doc.status="active"; db.commit(); return ok(row(doc))

@app.post("/api/v1/knowledge/documents/{document_id}/deactivate")
def deactivate_knowledge_document(document_id:str,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
    doc=db.get(KnowledgeDocument,document_id)
    if not doc: raise HTTPException(404,"Knowledge document not found")
    doc.status="inactive";doc.review_status="suspended"; audit(db,user,"deactivate_knowledge_document","knowledge_document",doc.id); db.commit(); return ok(row(doc))

@app.get("/api/v1/knowledge/documents")
def list_knowledge_documents(user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)): return ok([row(x) for x in db.query(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc())])

@app.get("/api/v1/knowledge/ingestion-jobs")
def list_ingestion_jobs(user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 return ok([row(x) for x in db.query(KnowledgeIngestionJob).order_by(KnowledgeIngestionJob.created_at.desc()).limit(200)])

@app.post("/api/v1/knowledge/documents/{document_id}/submit-review")
def submit_knowledge_review(document_id:str,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 doc=db.get(KnowledgeDocument,document_id)
 if not doc: raise HTTPException(404,"Knowledge document not found")
 if doc.status not in {"uploaded","indexed","failed"}: raise HTTPException(400,"Document cannot be submitted in its current state")
 doc.status="review_pending";doc.review_status="pending";audit(db,user,"submit_knowledge_review","knowledge_document",doc.id);db.commit();return ok(row(doc))

@app.post("/api/v1/knowledge/documents/{document_id}/approve")
def approve_knowledge_document(document_id:str,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
 doc=db.get(KnowledgeDocument,document_id)
 if not doc: raise HTTPException(404,"Knowledge document not found")
 if doc.status not in {"review_pending","indexed"}: raise HTTPException(400,"Document must be indexed or pending review")
 if not db.query(KnowledgeChunk).filter_by(document_id=doc.id).count(): raise HTTPException(400,"Document must be indexed before approval")
 if doc.source_type=="official_public_document": _require_governed_official_source(db,doc)
 doc.status="active";doc.review_status="approved";doc.reviewed_by=user.id;audit(db,user,"approve_knowledge_document","knowledge_document",doc.id);db.commit();return ok(row(doc))

@app.post("/api/v1/knowledge/query")
def knowledge_query(query:str=Form(...), top_k:int=Form(5), document_type:str|None=Form(None), jurisdiction:str|None=Form(None), product_mode:str=Form("domestic_beijing"), include_history:bool=Form(False), user:User=Depends(current_user), db:Session=Depends(get_db)):
    community=None
    if user.role=="resident":
        binding=db.query(Binding).filter_by(user_id=user.id,is_primary=True).first()
        if binding: community=db.get(Property,binding.property_id).community_name
    if include_history and user.role not in {"manager","customer_service"}: raise HTTPException(403,"Only staff may retrieve historical documents")
    return ok(search(db,query,user,community,min(max(top_k,1),10),include_history,document_type,jurisdiction,product_mode))

@app.get("/api/v1/product-context")
def product_context(user:User=Depends(current_user)):
    return ok({
        "default_mode":settings.product_mode,
        "supported_modes":["domestic_beijing","international_research","demo_garden"],
        "default_jurisdiction":settings.default_domestic_jurisdiction,
        "data_layers":{
            "KB_POLICY":"全国与北京官方法规、标准、指南，可用于有证据回答",
            "OPS_PUBLIC":"官方聚合公开数据，仅用于类别与趋势分析",
            "DEMO_SYNTHETIC":"合成业务数据，不代表真实居民、账单、小区或物业企业",
        },
        "real_property_authorization":False,
    })

@app.post("/api/v1/knowledge/feedback")
def knowledge_feedback(query_log_id:str=Form(...), rating:int=Form(...), comment:str|None=Form(None), user:User=Depends(current_user),db:Session=Depends(get_db)):
 if rating not in {-1,1}: raise HTTPException(400,"rating must be 1 or -1")
 if not db.query(RagQueryLog).filter_by(id=query_log_id,user_id=user.id).first(): raise HTTPException(404,"Query log not found")
 feedback=RagFeedback(rag_query_log_id=query_log_id,user_id=user.id,helpful=rating==1,feedback_type="helpful" if rating==1 else "not_helpful",comment=(comment or "")[:1000]);db.add(feedback);audit(db,user,"rag_feedback","rag_query_log",query_log_id);db.commit();return ok(row(feedback))
