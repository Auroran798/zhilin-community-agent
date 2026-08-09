from datetime import timedelta
import uuid
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException
from .models import *
from domain.state_machines.work_order import transition, TransitionError
from .time import as_utc, utc_now
from .idempotency import claim, complete, storage_key

def number(prefix:str, db:Session, model)->str:
    day=utc_now().strftime("%Y%m%d"); return f"{prefix}-{day}-{uuid.uuid4().hex[:8].upper()}"
def audit(db, actor, action, resource_type, resource_id, result="success", reason=None, request_id="system"):
    db.add(AuditLog(actor_id=getattr(actor,"id",None),actor_role=getattr(actor,"role",None),action=action,resource_type=resource_type,resource_id=resource_id,result=result,failure_reason=reason,request_id=request_id))

def bound_property(db,user,property_id):
    if user.role=="resident" and not db.query(Binding).filter_by(user_id=user.id,property_id=property_id).first(): raise HTTPException(403,"无权访问该房屋")
    return db.get(Property,property_id)

def sla_overdue(order):
    from .stage7 import SLAService
    return order.status not in {"已关闭","已取消"} and "overdue" in SLAService.get_status(order).values()

class WorkOrderService:
 def create(self,db,user,data,key=None):
    bound_property(db,user,data.property_id)
    operation="work_order.create"
    idem,replay=claim(db,user,operation,key,data.model_dump(mode="json"))
    if replay:
        old=db.get(WorkOrder,idem.resource_id)
        if not old or old.requester_id!=user.id: raise HTTPException(409,"幂等结果不存在或不属于当前用户")
        return old
    manual=data.risk_level in {"high","critical"}; reason="高风险需人工升级" if manual else None
    o=WorkOrder(work_order_no=number("WO",db,WorkOrder),requester_id=user.id,**data.model_dump(),requires_manual_escalation=manual,manual_escalation_reason=reason,idempotency_key=storage_key(user.id,operation,key) if key else None)
    db.add(o); db.flush()
    from .stage7 import SLAService, notify
    SLAService.attach(db,o)
    db.add(WorkOrderEvent(work_order_id=o.id,event_type="created",to_status=o.status,operator_id=user.id,note="创建工单")); notify(db,user.id,"WORK_ORDER_CREATED","报修工单已创建",f"工单 {o.work_order_no} 已创建。","work_order",o.id); audit(db,user,"create_work_order","work_order",o.id); complete(idem,"work_order",o.id,{"work_order_no":o.work_order_no}); db.commit(); db.refresh(o); return o
 def change(self,db,user,o,target,note="",resolution=None):
    if resolution: o.resolution=resolution
    try: transition(o,target,user,note,db)
    except TransitionError as e: audit(db,user,"illegal_transition","work_order",o.id,"denied",str(e));db.commit();raise HTTPException(400,str(e))
    from .stage7 import SLAService, notify
    if target=="已受理" and not o.first_response_at:o.first_response_at=utc_now()
    SLAService.refresh_status(o)
    recipients={o.requester_id,o.assignee_id}-{None}
    for recipient in recipients:notify(db,recipient,"WORK_ORDER_COMPLETED" if target in {"已完成","已关闭"} else "WORK_ORDER_STATUS_CHANGED","工单状态更新",f"工单 {o.work_order_no} 已更新为 {target}。","work_order",f"{o.id}:{target}")
    audit(db,user,"transition_work_order","work_order",o.id);db.commit();db.refresh(o);return o

class DashboardService:
 def summary(self,db):
    orders=db.query(WorkOrder).all(); total=len(orders); closed=[x for x in orders if x.status=="已关闭"]; ratings=db.query(WorkOrderRating).all()
    from .stage7 import SLAService
    statuses=[SLAService.get_status(x) for x in orders]
    result={"work_order_total":total,"today_new":sum(as_utc(x.created_at).date()==utc_now().date() for x in orders),"by_status":{s:sum(x.status==s for x in orders) for s in ["待受理","处理中","等待配件","待居民确认","已完成","已关闭"]},"overdue":sum("overdue" in x.values() for x in statuses),"sla_warning":sum("warning" in x.values() for x in statuses),"completion_rate":round(len(closed)/total*100,2) if total else 0,"average_rating":round(sum(x.score for x in ratings)/len(ratings),2) if ratings else None,"category_distribution":dict(db.query(WorkOrder.category,func.count()).group_by(WorkOrder.category).all()),"building_distribution":dict(db.query(Property.building_no,func.count(WorkOrder.id)).join(WorkOrder,WorkOrder.property_id==Property.id).group_by(Property.building_no).all()),"maintenance_workload":dict(db.query(User.display_name,func.count(WorkOrder.id)).join(WorkOrder,WorkOrder.assignee_id==User.id).group_by(User.display_name).all())}
    from .models import Announcement, BillReviewRequest, Equipment, InspectionTask, RectificationOrder
    result.update({"announcements":{"draft":db.query(Announcement).filter_by(status="draft").count(),"pending_review":db.query(Announcement).filter_by(status="pending_review").count(),"published":db.query(Announcement).filter_by(status="published").count()},"billing":{"pending_review":db.query(BillReviewRequest).filter(BillReviewRequest.status.in_(["submitted","under_review","pending"])).count(),"resolved":db.query(BillReviewRequest).filter(BillReviewRequest.status.in_(["resolved","handled"])).count()},"inspection":{"today_tasks":sum(as_utc(x.scheduled_at).date()==utc_now().date() for x in db.query(InspectionTask).all()),"open_rectifications":db.query(RectificationOrder).filter(RectificationOrder.status!="已关闭").count(),"overdue_rectifications":sum(as_utc(x.deadline)<utc_now() and x.status!="已关闭" for x in db.query(RectificationOrder).all())},"equipment":{"total":db.query(Equipment).count(),"abnormal":db.query(Equipment).filter(Equipment.status!="normal").count(),"high_frequency":dict(db.query(WorkOrder.equipment_id,func.count(WorkOrder.id)).filter(WorkOrder.equipment_id.is_not(None)).group_by(WorkOrder.equipment_id).having(func.count(WorkOrder.id)>=2).all())}})
    from .config import settings
    if settings.data_mode=="public_real":
        from .models import PublicCase
        result["public_real"]={"total":db.query(func.count(PublicCase.id)).scalar() or 0,"by_dataset":dict(db.query(PublicCase.source_dataset_id,func.count(PublicCase.id)).group_by(PublicCase.source_dataset_id).all()),"by_category":dict(db.query(PublicCase.normalized_category,func.count(PublicCase.id)).group_by(PublicCase.normalized_category).all()),"notice":"Historical public regulatory records, separate from synthetic tenant work orders."}
    return result
