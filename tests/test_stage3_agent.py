from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from decimal import Decimal
from api.main import app
from api.database import Base, get_db
from api.models import User, Property, Binding, WorkOrder, AgentStaffReview, AgentToolCall, Announcement, Bill, InspectionTask, InspectionRecord, RectificationOrder, WorkOrderRating
from api.security import hash_password

def _client(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'agent.db'}",connect_args={"check_same_thread":False});Base.metadata.create_all(engine);Session=sessionmaker(bind=engine)
    db=Session(); resident=User(username="resident",password_hash=hash_password("x"),display_name="居民",role="resident"); other=User(username="other",password_hash=hash_password("x"),display_name="其他居民",role="resident")
    prop=Property(community_name="测试小区",building_no="1",unit_no="1",room_no="101",floor=1);db.add_all([resident,other,prop]);db.flush();db.add(Binding(user_id=resident.id,property_id=prop.id));db.commit()
    def override():
        session=Session()
        try: yield session
        finally: session.close()
    app.dependency_overrides[get_db]=override
    client=TestClient(app)
    def header(name): return {"Authorization":"Bearer "+client.post("/api/v1/auth/login",json={"username":name,"password":"x"}).json()["data"]["access_token"]}
    return client,db,header,resident,other

def test_agent_repair_confirmation_is_idempotent(tmp_path):
    client,db,header,resident,_=_client(tmp_path)
    session=client.post("/api/v1/agent/sessions",headers=header("resident")).json()["data"]
    first=client.post(f"/api/v1/agent/sessions/{session['id']}/messages",headers=header("resident"),json={"content":"1号楼楼道灯不亮，请帮我报修"}).json()["data"]
    assert first["status"]=="awaiting_confirmation" and first["preview"]["action"]=="create_work_order"
    done=client.post(f"/api/v1/agent/confirmations/{first['confirmation_id']}",headers=header("resident"),json={"decision":"confirm"}).json()["data"]
    assert done["status"]=="completed" and db.query(WorkOrder).count()==1 and db.query(AgentToolCall).count()==1
    repeated=client.post(f"/api/v1/agent/confirmations/{first['confirmation_id']}",headers=header("resident"),json={"decision":"confirm"}).json()["data"]
    assert repeated["idempotent"] is True and db.query(WorkOrder).count()==1
    app.dependency_overrides.clear();db.close()

def test_agent_modify_cancel_memory_and_state(tmp_path):
    client,db,header,resident,_=_client(tmp_path)
    session=client.post("/api/v1/agent/sessions",headers=header("resident")).json()["data"]
    first=client.post(f"/api/v1/agent/sessions/{session['id']}/messages",headers=header("resident"),json={"content":"1号楼楼道灯不亮，请帮我报修"}).json()["data"]
    changed=client.post(f"/api/v1/agent/confirmations/{first['confirmation_id']}/modify",headers=header("resident"),json={"fields":{"location_description":"1号楼2单元门口"}}).json()["data"]
    assert changed["status"]=="awaiting_confirmation" and "2单元" in changed["preview"]["location_description"]
    cancelled=client.post(f"/api/v1/agent/confirmations/{changed['confirmation_id']}/cancel",headers=header("resident")).json()["data"]
    assert cancelled["status"]=="cancelled" and db.query(WorkOrder).count()==0
    assert client.put("/api/v1/agent/memories",headers=header("resident"),json={"memory_key":"service_preference","value":"短信提醒","consented":False}).status_code==400
    memory=client.put("/api/v1/agent/memories",headers=header("resident"),json={"memory_key":"service_preference","value":"短信提醒","consented":True}).json()["data"]
    assert client.get(f"/api/v1/agent/sessions/{session['id']}/state",headers=header("resident")).status_code==200
    assert client.delete(f"/api/v1/agent/memories/{memory['id']}",headers=header("resident")).status_code==200
    app.dependency_overrides.clear();db.close()

def test_agent_merges_follow_up_fields_before_confirmation(tmp_path):
    client,db,header,_,_=_client(tmp_path)
    session=client.post("/api/v1/agent/sessions",headers=header("resident")).json()["data"]
    first=client.post(f"/api/v1/agent/sessions/{session['id']}/messages",headers=header("resident"),json={"content":"我们楼里的电梯坏了"}).json()["data"]
    assert first["status"]=="need_information" and "是否有人被困" in first["answer"]
    second=client.post(f"/api/v1/agent/sessions/{session['id']}/messages",headers=header("resident"),json={"content":"5号楼，没有人被困，就是运行时有异响"}).json()["data"]
    assert second["status"]=="awaiting_confirmation"
    assert second["extracted_fields"]["category"]=="电梯"
    assert second["extracted_fields"]["is_trapped"]=="否"
    assert "5号楼" in second["action_preview"]["location_description"]
    app.dependency_overrides.clear();db.close()

def test_agent_announcement_draft_and_bill_explanation(tmp_path):
    client,db,header,resident,_=_client(tmp_path)
    service=User(username="service",password_hash=hash_password("x"),display_name="客服",role="customer_service")
    prop=db.query(Property).first()
    db.add_all([service,Bill(bill_no="B-202607",property_id=prop.id,billing_period="2026-07",bill_type="物业费",amount=Decimal("300.00"),paid_amount=Decimal("0"),status="unpaid",due_date=datetime.utcnow()+timedelta(days=1)),Bill(bill_no="B-202608",property_id=prop.id,billing_period="2026-08",bill_type="物业费",amount=Decimal("356.00"),paid_amount=Decimal("0"),status="unpaid",due_date=datetime.utcnow()+timedelta(days=1))]);db.commit()
    resident_session=client.post("/api/v1/agent/sessions",headers=header("resident")).json()["data"]
    bill=client.post(f"/api/v1/agent/sessions/{resident_session['id']}/messages",headers=header("resident"),json={"content":"为什么我这个月物业费比上个月多？"}).json()["data"]
    assert bill["intent"]=="bill_explanation" and bill["tool_result"]["comparison"]["difference"]=="56.00"
    service_session=client.post("/api/v1/agent/sessions",headers=header("service")).json()["data"]
    draft=client.post(f"/api/v1/agent/sessions/{service_session['id']}/messages",headers=header("service"),json={"content":"写一个明天上午9点到12点停水的公告，影响3号楼和4号楼，原因是水泵维修"}).json()["data"]
    assert draft["status"]=="awaiting_confirmation" and draft["preview"]["group_content"]
    done=client.post(f"/api/v1/agent/confirmations/{draft['confirmation_id']}/confirm",headers=header("service")).json()["data"]
    assert done["status"]=="completed" and db.query(Announcement).count()==1 and db.query(Announcement).first().status=="draft"
    app.dependency_overrides.clear();db.close()

def test_agent_inspection_record_and_electrical_water_risk(tmp_path):
    client,db,header,_,_=_client(tmp_path)
    manager=User(username="manager",password_hash=hash_password("x"),display_name="经理",role="manager")
    worker=User(username="worker",password_hash=hash_password("x"),display_name="巡检员",role="maintenance")
    db.add_all([manager,worker]);db.flush();task=InspectionTask(task_no="IT-AGENT-01",area_type="public_area",location_description="儿童活动区",scheduled_at=datetime.utcnow(),assignee_id=worker.id,created_by=manager.id);db.add(task);db.commit()
    session=client.post("/api/v1/agent/sessions",headers=header("worker")).json()["data"]
    normal=client.post(f"/api/v1/agent/sessions/{session['id']}/messages",headers=header("worker"),json={"content":"儿童滑梯有一个螺丝松了"}).json()["data"]
    assert normal["status"]=="awaiting_confirmation" and normal["preview"]["action"]=="submit_inspection_record"
    done=client.post(f"/api/v1/agent/confirmations/{normal['confirmation_id']}/confirm",headers=header("worker")).json()["data"]
    assert done["status"]=="completed" and db.query(InspectionRecord).count()==1 and db.query(RectificationOrder).count()==1
    risk=client.post(f"/api/v1/agent/sessions/{session['id']}/messages",headers=header("worker"),json={"content":"地下车库B区有大面积积水，已经接近配电柜"}).json()["data"]
    assert risk["status"]=="manual_review" and db.query(AgentStaffReview).count()==1
    app.dependency_overrides.clear();db.close()

def test_agent_can_cancel_and_rate_own_work_order(tmp_path):
    client,db,header,resident,_=_client(tmp_path)
    prop=db.query(Property).first()
    cancelled=WorkOrder(work_order_no="WO-20260803-0001",requester_id=resident.id,property_id=prop.id,original_description="灯坏",summary="照明报修",category="公共照明",location_description="1号楼楼道",fault_description="灯坏",contact_phone_masked="138****0000")
    completed=WorkOrder(work_order_no="WO-20260803-0002",requester_id=resident.id,property_id=prop.id,original_description="门禁",summary="门禁报修",category="门禁",location_description="1号楼门口",fault_description="门禁坏",contact_phone_masked="138****0000",status="已完成",completed_at=datetime.utcnow())
    db.add_all([cancelled,completed]);db.commit()
    session=client.post("/api/v1/agent/sessions",headers=header("resident")).json()["data"]
    cancel=client.post(f"/api/v1/agent/sessions/{session['id']}/messages",headers=header("resident"),json={"content":"取消工单 WO-20260803-0001"}).json()["data"]
    assert cancel["status"]=="awaiting_confirmation"
    assert client.post(f"/api/v1/agent/confirmations/{cancel['confirmation_id']}/confirm",headers=header("resident")).json()["data"]["status"]=="completed"
    assert db.get(WorkOrder,cancelled.id).status=="已取消"
    rating=client.post(f"/api/v1/agent/sessions/{session['id']}/messages",headers=header("resident"),json={"content":"给工单 WO-20260803-0002 打5分"}).json()["data"]
    assert rating["status"]=="awaiting_confirmation" and rating["preview"]["action"]=="rate_work_order"
    assert client.post(f"/api/v1/agent/confirmations/{rating['confirmation_id']}/confirm",headers=header("resident")).json()["data"]["status"]=="completed"
    assert db.query(WorkOrderRating).filter_by(work_order_id=completed.id).count()==1
    app.dependency_overrides.clear();db.close()

def test_agent_knowledge_answer_preserves_rag_citation(tmp_path):
    client,db,header,_,_=_client(tmp_path)
    manager=User(username="kb_manager",password_hash=hash_password("x"),display_name="知识管理员",role="manager")
    db.add(manager);db.commit()
    uploaded=client.post("/api/v1/knowledge/documents",headers=header("kb_manager"),data={"title":"测试小区装修管理规定","document_type":"renovation_rule","applicable_community":"测试小区","version":"1.0"},files={"file":("rule.md","# 第五条 装修时间\n周末不得进行产生噪声的装修施工。","text/markdown")})
    assert uploaded.status_code==200
    doc=uploaded.json()["data"]
    assert client.post(f"/api/v1/knowledge/documents/{doc['id']}/index",headers=header("kb_manager")).status_code==200
    session=client.post("/api/v1/agent/sessions",headers=header("resident")).json()["data"]
    answer=client.post(f"/api/v1/agent/sessions/{session['id']}/messages",headers=header("resident"),json={"content":"周末可以装修吗？"}).json()["data"]
    assert answer["intent"]=="knowledge_question" and answer["citations"]
    citation=answer["citations"][0]
    assert citation["title"]=="测试小区装修管理规定" and citation["version"]=="1.0" and citation["section"]
    app.dependency_overrides.clear();db.close()

def test_high_risk_review_can_be_assigned_and_resolved(tmp_path):
    client,db,header,_,_=_client(tmp_path)
    manager=User(username="review_manager",password_hash=hash_password("x"),display_name="经理",role="manager")
    service=User(username="review_service",password_hash=hash_password("x"),display_name="客服",role="customer_service")
    db.add_all([manager,service]);db.commit()
    session=client.post("/api/v1/agent/sessions",headers=header("resident")).json()["data"]
    risk=client.post(f"/api/v1/agent/sessions/{session['id']}/messages",headers=header("resident"),json={"content":"闻到煤气味，可能燃气泄漏"}).json()["data"]
    review_id=risk["staff_review_id"]
    assigned=client.post(f"/api/v1/agent/human-reviews/{review_id}/assign",headers=header("review_manager"),json={"assignee_id":service.id})
    assert assigned.status_code==200 and assigned.json()["data"]["status"]=="assigned"
    resolved=client.post(f"/api/v1/agent/human-reviews/{review_id}/resolve",headers=header("review_service"),json={"result":"已联系值班物业按应急流程处置"})
    assert resolved.status_code==200 and resolved.json()["data"]["status"]=="resolved"
    app.dependency_overrides.clear();db.close()

def test_agent_missing_risk_and_session_isolation(tmp_path):
    client,db,header,resident,other=_client(tmp_path)
    session=client.post("/api/v1/agent/sessions",headers=header("resident")).json()["data"]
    missing=client.post(f"/api/v1/agent/sessions/{session['id']}/messages",headers=header("resident"),json={"content":"灯坏了，帮我报修"}).json()["data"]
    assert missing["status"]=="need_information"
    risk=client.post(f"/api/v1/agent/sessions/{session['id']}/messages",headers=header("resident"),json={"content":"电梯里有人出不来，快处理"}).json()["data"]
    assert risk["status"]=="manual_review" and db.query(AgentStaffReview).count()==1
    assert client.get(f"/api/v1/agent/sessions/{session['id']}",headers=header("other")).status_code==404
    app.dependency_overrides.clear();db.close()
