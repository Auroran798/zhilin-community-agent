"""Stage 7 acceptance tests: four business closures and non-negotiable guards."""
from datetime import timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import api.main as main
from api.database import Base, get_db
from api.models import (Bill, BillItem, Binding, Equipment, InspectionPlan,
                        MaintenanceProfile, MaintenanceProfileSkill,
                        MaintenanceSkill, Notification, Property, SLAPolicy,
                        User, WorkOrder)
from api.security import create_token, hash_password
from api.time import utc_now
from harness.service import ExecutionContext, get_harness


def setup(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'stage7.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    resident = User(username="resident", password_hash=hash_password("x"), display_name="居民", role="resident")
    service = User(username="service", password_hash=hash_password("x"), display_name="客服", role="customer_service")
    worker = User(username="worker", password_hash=hash_password("x"), display_name="维修员", role="maintenance")
    manager = User(username="manager", password_hash=hash_password("x"), display_name="经理", role="manager")
    other = User(username="other", password_hash=hash_password("x"), display_name="另一住户", role="resident")
    property_row = Property(community_name="测试小区", building_no="3", unit_no="1", room_no="301", floor=3)
    other_property = Property(community_name="测试小区", building_no="1", unit_no="1", room_no="101", floor=1)
    db.add_all([resident, service, worker, manager, other, property_row, other_property]); db.flush()
    db.add_all([Binding(user_id=resident.id, property_id=property_row.id), Binding(user_id=other.id, property_id=other_property.id)])
    db.add_all([SLAPolicy(name="普通", category=None, risk_level="low", response_minutes=60, processing_minutes=240), SLAPolicy(name="紧急", category=None, risk_level="high", response_minutes=5, processing_minutes=30)])
    db.add_all([MaintenanceSkill(code="elevator", name="电梯"), MaintenanceSkill(code="general", name="综合")])
    db.add(MaintenanceProfile(user_id=worker.id, employee_code="M-001", display_name="维修员", service_area="3", current_workload=1))
    db.add_all([MaintenanceProfileSkill(profile_user_id=worker.id, skill_code="elevator"), MaintenanceProfileSkill(profile_user_id=worker.id, skill_code="general")])
    equipment = Equipment(equipment_code="EQ-3-01", name="3栋1号电梯", category="elevator", property_id=property_row.id, location="3号楼电梯厅")
    db.add(equipment); db.flush()
    previous = Bill(bill_no="B-PREV", property_id=property_row.id, billing_period="2026-07", bill_type="property_fee", amount=Decimal("120.00"), paid_amount=Decimal("120.00"), status="paid", due_date=utc_now()+timedelta(days=1))
    current = Bill(bill_no="B-CURRENT", property_id=property_row.id, billing_period="2026-08", bill_type="property_fee", amount=Decimal("150.00"), paid_amount=Decimal("0"), status="unpaid", due_date=utc_now()+timedelta(days=1))
    hidden = Bill(bill_no="B-HIDDEN", property_id=other_property.id, billing_period="2026-08", bill_type="property_fee", amount=Decimal("999.00"), paid_amount=Decimal("0"), status="unpaid", due_date=utc_now()+timedelta(days=1))
    db.add_all([previous, current, hidden]); db.flush()
    db.add_all([BillItem(bill_id=previous.id, item_type="property_fee", item_name="物业服务费", amount=Decimal("100.00")), BillItem(bill_id=previous.id, item_type="public_energy", item_name="公共能耗费", amount=Decimal("20.00")), BillItem(bill_id=current.id, item_type="property_fee", item_name="物业服务费", amount=Decimal("120.00")), BillItem(bill_id=current.id, item_type="public_energy", item_name="公共能耗费", amount=Decimal("30.00"))])
    db.commit()
    def override():
        session = Session()
        try:
            yield session
        finally:
            session.close()
    main.app.dependency_overrides[get_db] = override
    client = TestClient(main.app)
    headers = {name: {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={"username": name, "password": "x"}).json()["data"]["access_token"]} for name in ("resident", "service", "worker", "manager", "other")}
    return client, db, headers, {"resident": resident, "service": service, "worker": worker, "manager": manager, "property": property_row, "equipment": equipment, "current": current, "previous": previous, "hidden": hidden}


def teardown(db):
    main.app.dependency_overrides.clear(); db.close()


def test_e2e_repair_sla_recommend_assignment_and_rating(tmp_path):
    client, db, h, ids = setup(tmp_path)
    try:
        body = {"property_id": ids["property"].id, "original_description": "3栋电梯经常卡住", "summary": "电梯卡顿", "category": "电梯", "location_description": "3栋1号电梯", "fault_description": "频繁卡住", "equipment_id": ids["equipment"].id}
        order = client.post("/api/v1/work-orders", json=body, headers=h["resident"]).json()["data"]
        assert order["response_deadline"] and order["sla_policy_id"]
        assert client.post(f"/api/v1/work-orders/{order['id']}/accept", headers=h["service"]).status_code == 200
        recommendation = client.get(f"/api/v1/work-orders/{order['id']}/assignee-recommendation", headers=h["service"]).json()["data"]
        assert recommendation["recommended_user_id"] == ids["worker"].id and recommendation["skill_match"]
        assert client.post(f"/api/v1/work-orders/{order['id']}/assign", json={"assignee_id": ids["worker"].id}, headers=h["service"]).status_code == 200
        assert client.post(f"/api/v1/work-orders/{order['id']}/transition", json={"target_status": "处理中"}, headers=h["worker"]).status_code == 200
        assert client.post(f"/api/v1/work-orders/{order['id']}/transition", json={"target_status": "待居民确认", "resolution": "已检修并恢复运行"}, headers=h["worker"]).status_code == 200
        assert client.post(f"/api/v1/work-orders/{order['id']}/transition", json={"target_status": "已完成"}, headers=h["resident"]).status_code == 200
        assert client.post(f"/api/v1/work-orders/{order['id']}/rating", json={"score": 5}, headers=h["resident"]).status_code == 200
        assert len(client.get(f"/api/v1/work-orders/{order['id']}/timeline", headers=h["resident"]).json()["data"]) >= 6
    finally: teardown(db)


def test_e2e_announcement_approval_targeted_notification(tmp_path):
    client, db, h, ids = setup(tmp_path)
    try:
        draft = client.post("/api/v1/announcements", json={"title": "3栋停水维修通知", "announcement_type": "water_outage", "content": "明天下午停水维修。", "affected_scope": "3栋", "target_type": "building", "target_building_no": "3", "contact_information": "物业服务中心"}, headers=h["manager"]).json()["data"]
        assert client.post(f"/api/v1/announcements/{draft['id']}/submit-review", headers=h["manager"]).status_code == 200
        assert client.post(f"/api/v1/announcements/{draft['id']}/publish", headers=h["manager"]).status_code == 400
        assert client.post(f"/api/v1/announcements/{draft['id']}/approve", headers=h["manager"], json={"review_comment": "信息完整"}).status_code == 200
        assert client.post(f"/api/v1/announcements/{draft['id']}/publish", headers=h["manager"]).status_code == 200
        inbox = client.get("/api/v1/notifications", headers=h["resident"]).json()["data"]
        assert any(item["notification_type"] == "ANNOUNCEMENT_PUBLISHED" for item in inbox["items"])
        item = inbox["items"][0]
        assert client.post(f"/api/v1/notifications/{item['id']}/read", headers=h["resident"]).status_code == 200
    finally: teardown(db)


def test_e2e_bill_comparison_review_and_cross_user_block(tmp_path):
    client, db, h, ids = setup(tmp_path)
    try:
        comparison = client.get(f"/api/v1/bills/{ids['current'].id}/compare/{ids['previous'].id}", headers=h["resident"]).json()["data"]
        assert comparison["difference"] == "30.00" and len(comparison["changed_items"]) == 2
        assert client.get(f"/api/v1/bills/{ids['hidden'].id}/details", headers=h["resident"]).status_code == 403
        review = client.post(f"/api/v1/bills/{ids['current'].id}/review-requests", headers=h["resident"], json={"reason": "公共能耗费请核实"}).json()["data"]
        assert review["status"] == "submitted"
        assert client.post(f"/api/v1/bill-review-requests/{review['id']}/handle", headers=h["service"], json={"result": "已核验，为本月公共能耗分摊"}).status_code == 200
        assert any(x.notification_type == "BILL_REVIEW_RESULT" for x in db.query(Notification).filter_by(recipient_user_id=ids["resident"].id))
        assert "refund_payment" not in get_harness().registry and "reduce_fee" not in get_harness().registry
    finally: teardown(db)


def test_e2e_inspection_scheduler_rectification_equipment_and_security(tmp_path):
    client, db, h, ids = setup(tmp_path)
    try:
        plan = client.post("/api/v1/inspection-plans", headers=h["manager"], json={"name": "消防日巡", "category": "fire_safety", "target_type": "equipment", "target_id": ids["equipment"].id, "frequency": "daily", "assignee_id": ids["worker"].id, "next_run_at": (utc_now()-timedelta(minutes=1)).isoformat()}).json()["data"]
        first = client.post("/api/v1/scheduler/run-due", headers=h["manager"]).json()["data"]
        second = client.post("/api/v1/scheduler/run-due", headers=h["manager"]).json()["data"]
        assert first["inspection_tasks"] == 1 and second.get("idempotent") == 1
        task = next(x for x in client.get("/api/v1/inspection-tasks", headers=h["worker"]).json()["data"] if x["plan_id"] == plan["id"])
        record = client.post(f"/api/v1/inspection-tasks/{task['id']}/records", headers=h["worker"], json={"description": "消防设备压力异常", "abnormal": True, "risk_level": "critical"}).json()["data"]
        rect = client.post("/api/v1/rectification-orders", headers=h["manager"], json={"inspection_record_id": record["id"], "description": "修复消防设备", "risk_level": "critical", "deadline": (utc_now()+timedelta(days=1)).isoformat(), "equipment_id": ids["equipment"].id}).json()["data"]
        assert client.post(f"/api/v1/rectification-orders/{rect['id']}/assign", headers=h["manager"], json={"assignee_id": ids["worker"].id}).status_code == 200
        assert client.post(f"/api/v1/rectification-orders/{rect['id']}/complete", headers=h["worker"], json={"target_status": "待复查", "resolution": "已处理"}).status_code == 200
        assert client.post(f"/api/v1/rectification-orders/{rect['id']}/review", headers=h["service"], json={"target_status": "已关闭"}).status_code == 403
        assert client.post(f"/api/v1/rectification-orders/{rect['id']}/review", headers=h["manager"], json={"target_status": "已关闭", "note": "人工复查通过"}).status_code == 200
        history = client.get(f"/api/v1/equipment/{ids['equipment'].id}/history", headers=h["manager"]).json()["data"]
        assert any(x["id"] == rect["id"] for x in history["rectifications"])
        session = client.post("/api/v1/agent/sessions", headers=h["manager"]).json()["data"]
        equipment_query = client.post(f"/api/v1/agent/sessions/{session['id']}/messages", headers=h["manager"], json={"content": "查询设备台账"}).json()["data"]
        assert equipment_query["intent"] == "equipment_query" and equipment_query["tool_name"] == "search_equipment"
        denied = get_harness().execute(db, ExecutionContext(user_id=ids["resident"].id, role="resident", confirmed=True), "approve_announcement", {"announcement_id": "x"}, "s7-denied")
        assert not denied.ok and denied.error["code"] == "FORBIDDEN"
    finally: teardown(db)
