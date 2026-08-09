from api.models import WorkOrder, WorkOrderEvent
from api.time import utc_now

STATUSES = {"待补充信息","待受理","已受理","已派单","处理中","等待配件","待居民确认","已完成","已关闭","已取消"}
TRANSITIONS = {
 "待补充信息":{"待受理","已取消"}, "待受理":{"已受理","已取消"},
 "已受理":{"已派单"}, "已派单":{"处理中"}, "处理中":{"等待配件","待居民确认"},
 "等待配件":{"处理中"}, "待居民确认":{"处理中","已完成"},
 "已完成":{"已关闭","处理中"}, "已关闭":set(), "已取消":set()
}
ROLE_TARGETS = {
 "resident":{"已取消","已完成"},
 "customer_service":{"已受理","已派单","已取消"},
 "maintenance":{"处理中","等待配件","待居民确认"},
 "manager":{"已受理","已派单","已完成","已关闭","处理中"}
}
class TransitionError(ValueError): pass

def can_transition(current_status: str, target_status: str, actor_role: str) -> bool:
    return target_status in TRANSITIONS.get(current_status,set()) and target_status in ROLE_TARGETS.get(actor_role,set())

def transition(work_order: WorkOrder, target_status: str, actor, note: str, db) -> None:
    if target_status not in STATUSES or not can_transition(work_order.status,target_status,actor.role):
        raise TransitionError("工单状态或角色不允许该流转")
    if actor.role == "maintenance" and work_order.assignee_id != actor.id:
        raise TransitionError("维修人员只能处理分配给自己的工单")
    if target_status == "已派单" and not work_order.assignee_id:
        raise TransitionError("派单前必须指定处理人")
    if target_status == "待居民确认" and not work_order.resolution:
        raise TransitionError("提交待居民确认前必须填写处理结果")
    before=work_order.status; work_order.status=target_status; t=utc_now()
    if target_status=="已受理": work_order.accepted_at=t
    elif target_status=="已派单": work_order.assigned_at=t
    elif target_status=="处理中": work_order.started_at=work_order.started_at or t
    elif target_status=="待居民确认": work_order.completed_at=t
    elif target_status=="已关闭": work_order.closed_at=t
    db.add(WorkOrderEvent(work_order_id=work_order.id,event_type="status_changed",from_status=before,to_status=target_status,operator_id=actor.id,note=note))
