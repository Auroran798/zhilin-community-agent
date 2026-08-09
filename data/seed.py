"""Repeatable stage-1 synthetic data generator."""
from datetime import datetime, timedelta
from decimal import Decimal
from alembic import command
from alembic.config import Config
from api.database import SessionLocal
from api.models import *
from api.security import hash_password
from api.time import utc_now

SEED_VERSION = "stage1-v2"

def ensure_stage7(db):
    """Backfill Stage 7 reference data for a database seeded before Stage 7."""
    workers=db.query(User).filter_by(role="maintenance").order_by(User.username).all()
    managers=db.query(User).filter_by(role="manager").order_by(User.username).all()
    homes=db.query(Property).order_by(Property.building_no,Property.unit_no,Property.room_no).all()
    if not db.query(SLAPolicy).count():
        db.add_all([SLAPolicy(name="普通报修",category=None,risk_level="low",response_minutes=240,processing_minutes=4320),SLAPolicy(name="高优先级报修",category=None,risk_level="medium",response_minutes=60,processing_minutes=1440),SLAPolicy(name="紧急报修",category=None,risk_level="high",response_minutes=15,processing_minutes=240),SLAPolicy(name="重大安全事件",category=None,risk_level="critical",response_minutes=5,processing_minutes=120)])
    for code,name in [("plumbing","给排水"),("electrical","配电"),("elevator","电梯"),("fire_safety","消防"),("access_control","门禁"),("lighting","照明"),("general","综合维修")]:
        if not db.get(MaintenanceSkill,code):db.add(MaintenanceSkill(code=code,name=name))
    db.flush()
    for index,worker in enumerate(workers):
        if not db.get(MaintenanceProfile,worker.id):
            db.add(MaintenanceProfile(user_id=worker.id,employee_code=f"M-{index+1:03d}",display_name=worker.display_name,service_area="all" if index==0 else str((index%6)+1),current_workload=index%3))
    db.flush()
    for index,worker in enumerate(workers):
        if not db.get(MaintenanceProfileSkill,{"profile_user_id":worker.id,"skill_code":"general"}):db.add(MaintenanceProfileSkill(profile_user_id=worker.id,skill_code="general"))
        special=["elevator","plumbing","lighting","access_control","fire_safety","electrical","elevator","plumbing"][index%8]
        if not db.get(MaintenanceProfileSkill,{"profile_user_id":worker.id,"skill_code":special}):db.add(MaintenanceProfileSkill(profile_user_id=worker.id,skill_code=special))
    if homes and not db.query(Equipment).count():
        db.add_all([Equipment(equipment_code="EQ-3-ELEV-01",name="3栋1号电梯",category="elevator",property_id=homes[min(40,len(homes)-1)].id,location="3号楼电梯厅",manufacturer="DemoLift",model="DL-100"),Equipment(equipment_code="EQ-3-FIRE-01",name="3栋消防栓",category="fire_equipment",property_id=homes[min(40,len(homes)-1)].id,location="3号楼2层",manufacturer="DemoSafe",model="DS-20")])
    db.flush()
    for bill in db.query(Bill).all():
        if not db.query(BillItem).filter_by(bill_id=bill.id).count():db.add(BillItem(bill_id=bill.id,item_type="property_fee",item_name="物业服务费",amount=bill.amount,quantity=Decimal("1"),unit_price=bill.amount,description="模拟账单明细"))
    if workers and managers and not db.query(InspectionPlan).count():
        item=db.query(Equipment).filter_by(category="fire_equipment").first()
        db.add(InspectionPlan(name="消防设施周巡",category="fire_safety",target_type="equipment",target_id=item.id if item else None,frequency="weekly",assigned_role="maintenance",assignee_id=workers[0].id,next_run_at=utc_now(),created_by=managers[0].id))
    db.commit()

def seed():
    command.upgrade(Config("alembic.ini"), "head")
    db = SessionLocal()
    if db.query(User).first():
        ensure_stage7(db)
        print("Seed exists; no duplicate rows inserted.")
        return
    now = utc_now()
    password = hash_password("DemoPass123!")
    demo = [
        User(username="resident_demo", password_hash=password, display_name="Resident Demo", phone_masked="138****0001", role="resident"),
        User(username="service_demo", password_hash=password, display_name="Service Demo", phone_masked="139****0002", role="customer_service"),
        User(username="maintenance_demo", password_hash=password, display_name="Maintenance Demo", phone_masked="137****0003", role="maintenance"),
        User(username="manager_demo", password_hash=password, display_name="Manager Demo", phone_masked="136****0004", role="manager"),
    ]
    services = [demo[1]] + [User(username=f"service_{i}",password_hash=password,display_name=f"Service {i}",phone_masked="139****0000",role="customer_service") for i in range(1,3)]
    workers = [demo[2]] + [User(username=f"worker_{i}",password_hash=password,display_name=f"Worker {i}",phone_masked="137****0000",role="maintenance") for i in range(1,8)]
    managers = [demo[3]] + [User(username="manager_1",password_hash=password,display_name="Manager 1",phone_masked="136****0000",role="manager")]
    residents = [demo[0]] + [User(username=f"resident_{i:03d}",password_hash=password,display_name=f"Resident {i:03d}",phone_masked=f"138****{i:04d}",role="resident") for i in range(1,120)]
    db.add_all(residents + services + workers + managers); db.flush()
    # Stage 7 deterministic SLA and technician catalogue.  Values use natural
    # elapsed time, which is explicitly the Demo policy (no holiday calendar).
    db.add_all([
        SLAPolicy(name="普通报修",category=None,risk_level="low",response_minutes=240,processing_minutes=4320),
        SLAPolicy(name="高优先级报修",category=None,risk_level="medium",response_minutes=60,processing_minutes=1440),
        SLAPolicy(name="紧急报修",category=None,risk_level="high",response_minutes=15,processing_minutes=240),
        SLAPolicy(name="重大安全事件",category=None,risk_level="critical",response_minutes=5,processing_minutes=120),
    ])
    skill_rows=[MaintenanceSkill(code=code,name=name) for code,name in [("plumbing","给排水"),("electrical","配电"),("elevator","电梯"),("fire_safety","消防"),("access_control","门禁"),("lighting","照明"),("general","综合维修")]]
    db.add_all(skill_rows)
    for index, worker in enumerate(workers):
        db.add(MaintenanceProfile(user_id=worker.id,employee_code=f"M-{index+1:03d}",display_name=worker.display_name,service_area="all" if index==0 else str((index%6)+1),current_workload=index%3))
    db.flush()
    for worker in workers:
        db.add(MaintenanceProfileSkill(profile_user_id=worker.id,skill_code="general"))
    for index, code in enumerate(["elevator","plumbing","lighting","access_control","fire_safety","electrical","elevator","plumbing"]):
        db.add(MaintenanceProfileSkill(profile_user_id=workers[index].id,skill_code=code))
    homes = [Property(community_name="Demo Garden",building_no=str(b),unit_no=str(u),room_no=f"{floor:02d}01",floor=floor) for b in range(1,7) for u in (1,2) for floor in range(1,11)]
    db.add_all(homes); db.flush()
    db.add_all([Binding(user_id=residents[i].id,property_id=homes[i].id) for i in range(120)])
    equipment=[Equipment(equipment_code="EQ-3-ELEV-01",name="3栋1号电梯",category="elevator",property_id=homes[40].id,location="3号楼电梯厅",manufacturer="DemoLift",model="DL-100"),Equipment(equipment_code="EQ-3-FIRE-01",name="3栋消防栓",category="fire_equipment",property_id=homes[40].id,location="3号楼2层",manufacturer="DemoSafe",model="DS-20"),Equipment(equipment_code="EQ-1-PUMP-01",name="1栋供水泵",category="pump",property_id=homes[0].id,location="1号楼泵房",manufacturer="DemoPump",model="DP-5")]
    db.add_all(equipment);db.flush()
    categories=["Elevator","Water","Lighting","Access","Fire","Parking","Renovation","Cleaning","Electric","Road","Landscape","Other"]
    statuses=["待受理","已受理","已派单","处理中","等待配件","待居民确认","已完成","已关闭","已取消"]
    orders=[]
    for i in range(100):
        status=statuses[i%len(statuses)]; created=now-timedelta(hours=3*i+1)
        order=WorkOrder(work_order_no=f"WO-20260801-{i+1:04d}",requester_id=residents[i%120].id,property_id=homes[i%120].id,original_description=f"Building {(i%6)+1} {categories[i%12]} service request.",summary=f"{categories[i%12]} maintenance",category=categories[i%12],location_description=f"Building {(i%6)+1}",fault_description="Synthetic maintenance description.",risk_level="critical" if i%25==0 else ("medium" if i%4==0 else "low"),priority="P1" if i%25==0 else ("P2" if i%4==0 else "P3"),status=status,assignee_id=workers[i%8].id if status not in {"待受理","已受理","已取消"} else None,contact_phone_masked="138****0000",requires_manual_escalation=i%25==0,manual_escalation_reason="synthetic high risk" if i%25==0 else None,source_type="synthetic",created_at=created)
        if status not in {"待受理","已取消"}: order.accepted_at=created+timedelta(minutes=20)
        if order.assignee_id: order.assigned_at=created+timedelta(minutes=40)
        if status in {"处理中","等待配件","待居民确认","已完成","已关闭"}: order.started_at=created+timedelta(hours=1)
        if status in {"待居民确认","已完成","已关闭"}: order.completed_at=created+timedelta(hours=5)
        if status=="已关闭": order.closed_at=created+timedelta(hours=8)
        orders.append(order)
    db.add_all(orders);db.flush()
    for order in orders:
        db.add(WorkOrderEvent(work_order_id=order.id,event_type="created",to_status="待受理",operator_id=order.requester_id,note="synthetic"))
        db.add(WorkOrderEvent(work_order_id=order.id,event_type="current",to_status=order.status,operator_id=services[0].id,note="synthetic timeline"))
    for order in [o for o in orders if o.status in {"已完成","已关闭"}][:15]:
        db.add(WorkOrderRating(work_order_id=order.id,resident_id=order.requester_id,score=4,comment="Synthetic rating"))
    bills=[]
    for i,home in enumerate(homes[:24]):
        for month in range(3,7):
            paid=Decimal("120.00") if month<6 else Decimal("0.00")
            bills.append(Bill(bill_no=f"B-2026-{i:03d}-{month}",property_id=home.id,billing_period=f"2026-{month:02d}",bill_type="property_fee",amount=Decimal("120.00"),paid_amount=paid,status="paid" if paid else "unpaid",due_date=now+timedelta(days=15),source_type="synthetic"))
    db.add_all(bills);db.flush()
    db.add_all([BillItem(bill_id=b.id,item_type="property_fee",item_name="物业服务费",amount=Decimal("100.00"),quantity=Decimal("1"),unit_price=Decimal("100.00"),description="模拟物业服务费") for b in bills])
    db.add_all([BillItem(bill_id=b.id,item_type="public_energy",item_name="公共能耗费",amount=Decimal("20.00"),quantity=Decimal("1"),unit_price=Decimal("20.00"),description="模拟公共区域能耗分摊") for b in bills])
    db.add_all([PaymentRecord(bill_id=b.id,payment_no=f"PAY-{i:04d}",amount=b.paid_amount,paid_at=now-timedelta(days=i),payment_channel="mock",status="paid") for i,b in enumerate(bills) if b.paid_amount > 0][:48])
    db.add_all([BillReviewRequest(request_no=f"BR-2026-{i:04d}",bill_id=bills[-i-1].id,resident_id=residents[23-i].id,reason="Synthetic bill review",status="pending",created_at=now-timedelta(days=i)) for i in range(10)])
    db.add_all([Announcement(title=f"Synthetic notice {i}",announcement_type="notice",content="Synthetic announcement.",affected_scope="Demo Garden",contact_information="Property office",publisher_unit="Demo Garden",status="published",created_by=services[0].id,published_by=managers[0].id,published_at=now) for i in range(12)])
    tasks=[InspectionTask(task_no=f"IT-2026-{i:04d}",area_type="fire_safety",location_description=f"Building {(i%6)+1}",scheduled_at=now-timedelta(days=i),assignee_id=workers[i%8].id,status="assigned",created_by=managers[0].id) for i in range(14)]
    db.add_all(tasks);db.flush()
    records=[InspectionRecord(inspection_task_id=tasks[i].id,inspector_id=tasks[i].assignee_id,description="Synthetic abnormal inspection.",abnormal=True,risk_level="medium",submitted_at=now-timedelta(days=i)) for i in range(10)]
    db.add_all(records);db.flush()
    db.add_all([RectificationOrder(rectification_no=f"RO-2026-{i:04d}",inspection_record_id=records[i].id,description="Synthetic rectification.",risk_level="medium",status="待整改",assignee_id=workers[i%8].id,deadline=now+timedelta(days=2)) for i in range(8)])
    db.add_all([InspectionPlan(name="消防设施周巡",category="fire_safety",target_type="equipment",target_id=equipment[1].id,frequency="weekly",assigned_role="maintenance",assignee_id=workers[4].id,next_run_at=now,created_by=managers[0].id),InspectionPlan(name="电梯日巡",category="elevator",target_type="equipment",target_id=equipment[0].id,frequency="daily",assigned_role="maintenance",assignee_id=workers[0].id,next_run_at=now,created_by=managers[0].id)])
    db.add_all([AuditLog(actor_id=managers[0].id,actor_role="manager",action="seed",resource_type="seed",resource_id=None,request_id=f"seed-{i}",result="success",metadata_json=SEED_VERSION) for i in range(30)])
    db.commit()
    ensure_stage7(db)
    print(f"Seed {SEED_VERSION}: users={db.query(User).count()} properties={db.query(Property).count()} orders={db.query(WorkOrder).count()} bills={db.query(Bill).count()}")

if __name__=="__main__":
    seed()
