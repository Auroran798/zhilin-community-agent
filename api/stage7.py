"""Deterministic Stage 7 business services.

LLMs may phrase a request, but every deadline, recommendation, approval,
notification recipient and monetary comparison is calculated in this module.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    Announcement, AnnouncementApproval, Bill, BillItem, BillReviewRequest,
    Binding, Equipment, InspectionPlan, InspectionRecord, InspectionTask,
    MaintenanceProfile, MaintenanceProfileSkill, Notification, PaymentRecord,
    RectificationOrder, SchedulerJobRun, SLAPolicy, User, WorkOrder,
)
from .time import as_utc, utc_now

WARNING_RATIO = 0.20
SKILL_FOR_CATEGORY = {
    "给排水": "plumbing", "电梯": "elevator", "消防设施": "fire_safety",
    "门禁": "access_control", "公共照明": "lighting", "配电设施": "electrical",
}


def _number(prefix: str, at: datetime | None = None) -> str:
    instant = as_utc(at) if at else utc_now()
    return f"{prefix}-{instant:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _actor(actor: User | None) -> str | None:
    return actor.id if actor else None


def _audit(db: Session, actor: User | None, action: str, resource_type: str, resource_id: str | None, before: Any = None, after: Any = None) -> None:
    from .services import audit
    payload = json.dumps({"before": before, "after": after}, ensure_ascii=False, default=str)[:3500]
    audit(db, actor, action, resource_type, resource_id, reason=payload)


def notify(db: Session, recipient_user_id: str, notification_type: str, title: str, content: str, business_type: str, business_id: str) -> Notification:
    """Create exactly one notification for a business event and recipient."""
    key = f"{notification_type}:{business_type}:{business_id}:{recipient_user_id}"
    old = db.query(Notification).filter_by(idempotency_key=key).first()
    if old:
        return old
    item = Notification(recipient_user_id=recipient_user_id, notification_type=notification_type, title=title[:160], content=content[:4000], business_type=business_type, business_id=business_id, idempotency_key=key)
    db.add(item)
    return item


class SLAService:
    @staticmethod
    def select_policy(db: Session, category: str, risk_level: str) -> SLAPolicy | None:
        base = db.query(SLAPolicy).filter_by(enabled=True)
        return (base.filter_by(category=category, risk_level=risk_level).first()
                or base.filter_by(category=None, risk_level=risk_level).first()
                or base.filter_by(category=category, risk_level=None).first()
                or base.filter_by(category=None, risk_level=None).first())

    @staticmethod
    def calculate_response_deadline(created_at: datetime, policy: SLAPolicy) -> datetime:
        return as_utc(created_at) + timedelta(minutes=policy.response_minutes)

    @staticmethod
    def calculate_processing_deadline(created_at: datetime, policy: SLAPolicy) -> datetime:
        return as_utc(created_at) + timedelta(minutes=policy.processing_minutes)

    @classmethod
    def attach(cls, db: Session, order: WorkOrder) -> None:
        policy = cls.select_policy(db, order.category, order.risk_level)
        if not policy:
            return
        order.sla_policy_id = policy.id
        order.response_deadline = cls.calculate_response_deadline(order.created_at, policy)
        order.processing_deadline = cls.calculate_processing_deadline(order.created_at, policy)
        cls.refresh_status(order)

    @staticmethod
    def _status(deadline: datetime | None, started_at: datetime, now: datetime, finished_at: datetime | None = None) -> str:
        if finished_at:
            return "completed"
        if deadline is None:
            return "normal"
        deadline, started_at = as_utc(deadline), as_utc(started_at)
        if now >= deadline:
            return "overdue"
        total = max((deadline - started_at).total_seconds(), 1)
        return "warning" if (deadline - now).total_seconds() / total <= WARNING_RATIO else "normal"

    @classmethod
    def get_status(cls, order: WorkOrder, at: datetime | None = None) -> dict[str, Any]:
        now = as_utc(at) if at else utc_now()
        response = cls._status(order.response_deadline, order.created_at, now, order.first_response_at)
        processing = cls._status(order.processing_deadline, order.created_at, now, order.completed_at or order.closed_at)
        return {"response": response, "processing": processing, "response_deadline": order.response_deadline, "processing_deadline": order.processing_deadline}

    @classmethod
    def refresh_status(cls, order: WorkOrder, at: datetime | None = None) -> dict[str, Any]:
        statuses = cls.get_status(order, at)
        order.sla_response_status = statuses["response"]
        order.sla_processing_status = statuses["processing"]
        if "overdue" in {statuses["response"], statuses["processing"]} and not order.overdue_at:
            order.overdue_at = as_utc(at) if at else utc_now()
        return statuses


class AssignmentService:
    @staticmethod
    def recommend(db: Session, order: WorkOrder) -> dict[str, Any]:
        required_skill = SKILL_FOR_CATEGORY.get(order.category, "general")
        profiles = db.query(MaintenanceProfile).filter_by(enabled=True, availability_status="available").all()
        property_row = db.get(__import__("api.models", fromlist=["Property"]).Property, order.property_id)
        building = property_row.building_no if property_row else None
        ranked: list[tuple[int, MaintenanceProfile, bool, bool]] = []
        for profile in profiles:
            skills = {x.skill_code for x in db.query(MaintenanceProfileSkill).filter_by(profile_user_id=profile.user_id)}
            skill_match = required_skill in skills or "general" in skills
            if not skill_match:
                continue
            area_match = profile.service_area in {"", "all"} or (building and building in profile.service_area.split(","))
            score = 100 + (25 if area_match else 0) - profile.current_workload * 8
            ranked.append((score, profile, skill_match, area_match))
        if not ranked:
            return {"recommended_user_id": None, "reason": "没有具备所需技能且当前可用的维修人员", "required_skill": required_skill}
        _, profile, skill_match, area_match = sorted(ranked, key=lambda row: (-row[0], row[1].current_workload, row[1].employee_code))[0]
        return {"recommended_user_id": profile.user_id, "reason": "按技能匹配、服务区域、当前负载和可用状态排序；仍须人工确认派单。", "required_skill": required_skill, "skill_match": skill_match, "area_match": area_match, "workload": profile.current_workload, "availability": profile.availability_status}

    @staticmethod
    def assign(db: Session, actor: User, order: WorkOrder, assignee_id: str, note: str = "") -> WorkOrder:
        from .services import WorkOrderService
        assignee = db.get(User, assignee_id)
        profile = db.get(MaintenanceProfile, assignee_id)
        if not assignee or assignee.role != "maintenance":
            raise HTTPException(400, "处理人必须是启用的维修人员")
        # Older demo databases predate maintenance_profiles.  Promote an
        # existing maintenance login into a conservative default profile on
        # its first manually confirmed assignment instead of breaking its
        # already-authorised work queue.
        if not profile:
            profile = MaintenanceProfile(user_id=assignee.id, employee_code=f"LEGACY-{assignee.id[:8]}", display_name=assignee.display_name, service_area="all")
            db.add(profile); db.flush()
        if not profile.enabled:
            raise HTTPException(400, "处理人当前不可用")
        before = order.assignee_id
        order.assignee_id = assignee_id
        WorkOrderService().change(db, actor, order, "已派单", note or "人工确认派单")
        profile.current_workload += 1
        notify(db, assignee_id, "WORK_ORDER_ASSIGNED", "您有新的维修任务", f"工单 {order.work_order_no} 已人工派给您。", "work_order", order.id)
        _audit(db, actor, "assign_work_order", "work_order", order.id, {"assignee_id": before}, {"assignee_id": assignee_id})
        db.commit()
        return order


class AnnouncementService:
    @staticmethod
    def submit(db: Session, actor: User, announcement: Announcement) -> Announcement:
        if announcement.status != "draft":
            raise HTTPException(400, "仅草稿可提交审核")
        announcement.status = "pending_review"
        db.add(AnnouncementApproval(announcement_id=announcement.id, requested_by=actor.id))
        _audit(db, actor, "request_announcement_approval", "announcement", announcement.id, {"status": "draft"}, {"status": "pending_review"})
        db.commit()
        return announcement

    @staticmethod
    def approve(db: Session, actor: User, announcement: Announcement, decision: str = "approved", comment: str | None = None) -> Announcement:
        if announcement.status != "pending_review" or decision not in {"approved", "rejected"}:
            raise HTTPException(400, "公告未处于可审核状态")
        approval = db.query(AnnouncementApproval).filter_by(announcement_id=announcement.id, decision="pending").order_by(AnnouncementApproval.requested_at.desc()).first()
        if not approval:
            raise HTTPException(400, "缺少有效的人工审核申请")
        approval.reviewed_by, approval.decision, approval.review_comment, approval.reviewed_at = actor.id, decision, comment, utc_now()
        announcement.status = "approved" if decision == "approved" else "draft"
        announcement.reviewed_by, announcement.reviewed_at = actor.id, utc_now()
        _audit(db, actor, "approve_announcement" if decision == "approved" else "reject_announcement", "announcement", announcement.id, {"status": "pending_review"}, {"status": announcement.status})
        db.commit()
        return announcement

    @staticmethod
    def recipients(db: Session, announcement: Announcement) -> list[str]:
        q = db.query(Binding.user_id).join(__import__("api.models", fromlist=["Property"]).Property, Binding.property_id == __import__("api.models", fromlist=["Property"]).Property.id)
        if announcement.target_type == "building" and announcement.target_building_no:
            q = q.filter(__import__("api.models", fromlist=["Property"]).Property.building_no == announcement.target_building_no)
        return sorted({user_id for (user_id,) in q.all()})

    @classmethod
    def publish(cls, db: Session, actor: User, announcement: Announcement, *, commit: bool = True) -> Announcement:
        if announcement.status != "approved":
            raise HTTPException(400, "仅经人工审批的公告可以发布")
        announcement.status, announcement.published_by, announcement.published_at = "published", actor.id, utc_now()
        for recipient in cls.recipients(db, announcement):
            notify(db, recipient, "ANNOUNCEMENT_PUBLISHED", announcement.title, announcement.content, "announcement", announcement.id)
        _audit(db, actor, "publish_announcement", "announcement", announcement.id, {"status": "approved"}, {"status": "published"})
        from .outbox import enqueue_announcement_index
        enqueue_announcement_index(db, announcement, actor.id)
        db.commit() if commit else db.flush()
        return announcement

    @staticmethod
    def withdraw(db: Session, actor: User, announcement: Announcement) -> Announcement:
        if announcement.status != "published":
            raise HTTPException(400, "仅已发布公告可撤回")
        announcement.status = "cancelled"
        _audit(db, actor, "withdraw_announcement", "announcement", announcement.id, {"status": "published"}, {"status": "cancelled"})
        from .outbox import enqueue_announcement_index
        enqueue_announcement_index(db, announcement, actor.id)
        db.commit()
        return announcement


class BillingService:
    @staticmethod
    def assert_visible(db: Session, user: User, bill: Bill) -> None:
        if user.role == "resident" and not db.query(Binding).filter_by(user_id=user.id, property_id=bill.property_id).first():
            raise HTTPException(403, "无权访问该账单")

    @classmethod
    def details(cls, db: Session, user: User, bill_id: str) -> dict[str, Any]:
        bill = db.get(Bill, bill_id)
        if not bill:
            raise HTTPException(404, "账单不存在")
        cls.assert_visible(db, user, bill)
        items = db.query(BillItem).filter_by(bill_id=bill.id).all()
        paid = sum((p.amount for p in db.query(PaymentRecord).filter_by(bill_id=bill.id)), Decimal("0"))
        return {"bill": bill, "items": items, "paid_amount": paid, "balance": Decimal(bill.amount) - paid}

    @classmethod
    def compare(cls, db: Session, user: User, current_id: str, previous_id: str) -> dict[str, Any]:
        current, previous = db.get(Bill, current_id), db.get(Bill, previous_id)
        if not current or not previous:
            raise HTTPException(404, "账单不存在")
        cls.assert_visible(db, user, current); cls.assert_visible(db, user, previous)
        if current.property_id != previous.property_id:
            raise HTTPException(400, "只能比较同一房屋的账单")
        current_items = {x.item_name: Decimal(x.amount) for x in db.query(BillItem).filter_by(bill_id=current.id)}
        previous_items = {x.item_name: Decimal(x.amount) for x in db.query(BillItem).filter_by(bill_id=previous.id)}
        changed = [{"item_name": name, "current_amount": str(current_items.get(name, 0)), "previous_amount": str(previous_items.get(name, 0)), "difference": str(current_items.get(name, 0) - previous_items.get(name, 0))} for name in sorted(current_items.keys() | previous_items.keys()) if current_items.get(name, 0) != previous_items.get(name, 0)]
        return {"current_total": str(current.amount), "previous_total": str(previous.amount), "difference": str(Decimal(current.amount) - Decimal(previous.amount)), "changed_items": changed}

    @staticmethod
    def payment_history(db: Session, user: User, property_id: str) -> list[PaymentRecord]:
        if user.role == "resident" and not db.query(Binding).filter_by(user_id=user.id, property_id=property_id).first():
            raise HTTPException(403, "无权访问该房屋")
        return db.query(PaymentRecord).join(Bill, PaymentRecord.bill_id == Bill.id).filter(Bill.property_id == property_id).order_by(PaymentRecord.paid_at.desc()).all()


class InspectionService:
    @staticmethod
    def period_key(frequency: str, at: datetime) -> str:
        at = as_utc(at)
        if frequency == "daily": return at.strftime("%Y-%m-%d")
        if frequency == "weekly": return f"{at:%G}-W{at:%V}"
        if frequency == "monthly": return at.strftime("%Y-%m")
        raise HTTPException(400, "frequency 仅支持 daily、weekly 或 monthly")

    @staticmethod
    def next_run(plan: InspectionPlan, at: datetime) -> datetime:
        days = {"daily": 1, "weekly": 7, "monthly": 30}.get(plan.frequency)
        if not days: raise HTTPException(400, "无效巡检频率")
        return as_utc(at) + timedelta(days=days)

    @classmethod
    def generate_due(cls, db: Session, at: datetime | None = None) -> list[InspectionTask]:
        at = as_utc(at) if at else utc_now(); generated: list[InspectionTask] = []
        for plan in db.query(InspectionPlan).filter_by(enabled=True).all():
            if as_utc(plan.next_run_at) > at:
                continue
            if not plan.assignee_id:
                continue
            key = cls.period_key(plan.frequency, at)
            existing = db.query(InspectionTask).filter_by(plan_id=plan.id, period_key=key).first()
            if existing:
                plan.next_run_at = cls.next_run(plan, at)
                continue
            equipment = db.get(Equipment, plan.target_id) if plan.target_type == "equipment" and plan.target_id else None
            task = InspectionTask(task_no=_number("IT", at), area_type=plan.category, location_description=equipment.location if equipment else plan.target_type, scheduled_at=at, assignee_id=plan.assignee_id, created_by=plan.created_by, plan_id=plan.id, period_key=key, equipment_id=equipment.id if equipment else None)
            db.add(task); db.flush(); generated.append(task)
            plan.next_run_at = cls.next_run(plan, at)
            notify(db, plan.assignee_id, "INSPECTION_ASSIGNED", "您有新的巡检任务", f"巡检计划「{plan.name}」已生成任务。", "inspection_task", task.id)
        db.flush()
        return generated

    @staticmethod
    def create_rectification(db: Session, actor: User, record: InspectionRecord, deadline: datetime, equipment_id: str | None = None) -> RectificationOrder:
        old = db.query(RectificationOrder).filter_by(inspection_record_id=record.id).first()
        if old: return old
        item = RectificationOrder(rectification_no=_number("RO"), inspection_record_id=record.id, description=record.description, risk_level=record.risk_level, deadline=deadline, equipment_id=equipment_id)
        db.add(item); db.flush()
        _audit(db, actor, "create_rectification", "rectification", item.id, after={"risk_level": item.risk_level})
        return item


class EquipmentService:
    @staticmethod
    def history(db: Session, equipment_id: str) -> dict[str, Any]:
        item = db.get(Equipment, equipment_id)
        if not item: raise HTTPException(404, "设备不存在")
        return {"equipment": item, "work_orders": db.query(WorkOrder).filter_by(equipment_id=item.id).order_by(WorkOrder.created_at.desc()).all(), "inspection_tasks": db.query(InspectionTask).filter_by(equipment_id=item.id).order_by(InspectionTask.scheduled_at.desc()).all(), "rectifications": db.query(RectificationOrder).filter_by(equipment_id=item.id).order_by(RectificationOrder.created_at.desc()).all()}


class SchedulerService:
    @staticmethod
    def run_due(db: Session, actor: User | None = None, at: datetime | None = None) -> dict[str, int]:
        at = as_utc(at) if at else utc_now()
        run_key = f"due:{at:%Y%m%d%H%M}"
        previous = db.query(SchedulerJobRun).filter_by(run_key=run_key).first()
        if previous and previous.status == "completed":
            return json.loads(previous.result_json or "{}") | {"idempotent": 1}
        if previous and previous.status == "running":
            if previous.started_at and at - as_utc(previous.started_at) < timedelta(minutes=10):
                return {"in_progress": 1}
            previous.status = "failed"
            previous.error_message = "stale execution lease expired"
        run = previous or SchedulerJobRun(job_name="stage7_due_scan", run_key=run_key, status="running")
        run.status, run.error_message, run.finished_at = "running", None, None
        db.add(run)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            concurrent = db.query(SchedulerJobRun).filter_by(run_key=run_key).first()
            return json.loads(concurrent.result_json or "{}") | ({"idempotent": 1} if concurrent and concurrent.status == "completed" else {"in_progress": 1})
        try:
            generated = InspectionService.generate_due(db, at)
            sla_events = rect_events = published = 0
            for order in db.query(WorkOrder).filter(~WorkOrder.status.in_(["已关闭", "已取消"])).all():
                current = SLAService.refresh_status(order, at)
                for phase, status in (("response", current["response"]), ("processing", current["processing"])):
                    if status in {"warning", "overdue"}:
                        ntype = "SLA_WARNING" if status == "warning" else "SLA_OVERDUE"
                        for recipient in {order.requester_id, order.assignee_id} - {None}:
                            notify(db, recipient, ntype, "工单 SLA 提醒", f"工单 {order.work_order_no} 的{ '响应' if phase == 'response' else '处理'} SLA {status}。", "work_order", f"{order.id}:{phase}:{status}")
                        sla_events += 1
            for rect in db.query(RectificationOrder).filter(~RectificationOrder.status.in_(["已关闭"])).all():
                if as_utc(rect.deadline) <= at and rect.assignee_id:
                    notify(db, rect.assignee_id, "RECTIFICATION_DUE", "整改任务已到期", f"整改工单 {rect.rectification_no} 已到期，请尽快处理。", "rectification", rect.id)
                    rect_events += 1
            for announcement in db.query(Announcement).filter_by(status="approved").filter(Announcement.scheduled_publish_at.is_not(None)).all():
                if as_utc(announcement.scheduled_publish_at) <= at:
                    reviewer = actor or db.get(User, announcement.reviewed_by)
                    if not reviewer:
                        raise RuntimeError(f"公告 {announcement.id} 缺少有效审核人")
                    AnnouncementService.publish(db, reviewer, announcement, commit=False); published += 1
            result = {"inspection_tasks": len(generated), "sla_events": sla_events, "rectification_due": rect_events, "scheduled_announcements": published}
            run.status, run.result_json, run.finished_at = "completed", json.dumps(result), utc_now()
            _audit(db, actor, "run_scheduler_due_jobs", "scheduler_job", run.id, after=result)
            db.commit()
            return result
        except Exception as exc:
            db.rollback()
            failed = db.query(SchedulerJobRun).filter_by(run_key=run_key).first() or SchedulerJobRun(job_name="stage7_due_scan", run_key=run_key)
            failed.status, failed.error_message, failed.finished_at = "failed", f"{type(exc).__name__}: {exc}"[:2000], utc_now()
            db.add(failed); db.commit()
            raise
