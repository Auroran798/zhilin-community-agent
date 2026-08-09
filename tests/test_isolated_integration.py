from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.main import app
from api.database import Base, get_db
from api.models import User, Property, Binding, InspectionTask
from api.security import hash_password

@pytest.fixture()
def isolated_client(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path / 'test.db'}",connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine)
    db=Session()
    password=hash_password("DemoPass123!")
    resident=User(username="r",password_hash=password,display_name="居民",role="resident",phone_masked="138****0000")
    service=User(username="s",password_hash=password,display_name="客服",role="customer_service",phone_masked="138****0000")
    worker=User(username="w",password_hash=password,display_name="维修",role="maintenance",phone_masked="138****0000")
    manager=User(username="m",password_hash=password,display_name="经理",role="manager",phone_masked="138****0000")
    prop=Property(community_name="测试小区",building_no="1",unit_no="1",room_no="101",floor=1)
    db.add_all([resident,service,worker,manager,prop]);db.flush();db.add(Binding(user_id=resident.id,property_id=prop.id));db.add(InspectionTask(task_no="IT-TEST-0001",area_type="消防",location_description="1号楼",scheduled_at=datetime.utcnow(),assignee_id=worker.id,created_by=manager.id));db.commit()
    def override():
        session=Session()
        try: yield session
        finally: session.close()
    app.dependency_overrides[get_db]=override
    yield TestClient(app),{"resident":resident.id,"service":service.id,"worker":worker.id,"manager":manager.id,"property":prop.id}
    app.dependency_overrides.clear();db.close()

def login(client,name):
    return {"Authorization":"Bearer "+client.post("/api/v1/auth/login",json={"username":name,"password":"DemoPass123!"}).json()["data"]["access_token"]}

def test_isolated_work_order_closed_loop(isolated_client):
    client,ids=isolated_client;r=login(client,"r");s=login(client,"s");w=login(client,"w")
    p={"property_id":ids["property"],"original_description":"灯不亮","summary":"照明","category":"公共照明","location_description":"楼道","fault_description":"损坏"}
    order=client.post("/api/v1/work-orders",headers=r,json=p).json()["data"]
    assert client.post(f"/api/v1/work-orders/{order['id']}/accept",headers=s).status_code==200
    assert client.post(f"/api/v1/work-orders/{order['id']}/assign",headers=s,json={"assignee_id":ids["worker"]}).status_code==200
    for target,body in [("处理中",{}),("待居民确认",{"resolution":"已更换灯泡"})]:
        assert client.post(f"/api/v1/work-orders/{order['id']}/transition",headers=w,json={"target_status":target,**body}).status_code==200
    assert client.post(f"/api/v1/work-orders/{order['id']}/transition",headers=r,json={"target_status":"已完成"}).status_code==200

def test_isolated_inspection_rectification_loop(isolated_client):
    client,ids=isolated_client;w=login(client,"w");m=login(client,"m")
    task=client.get("/api/v1/inspection-tasks",headers=w).json()["data"][0]
    rec=client.post(f"/api/v1/inspection-tasks/{task['id']}/records",headers=w,json={"description":"通道堆物","abnormal":True,"risk_level":"medium"}).json()["data"]
    rect=client.post("/api/v1/rectification-orders",headers=m,json={"inspection_record_id":rec["id"],"description":"清理通道","risk_level":"medium","deadline":(datetime.utcnow()+timedelta(days=1)).isoformat()}).json()["data"]
    assert client.post(f"/api/v1/rectification-orders/{rect['id']}/assign",headers=m,json={"assignee_id":ids["worker"]}).status_code==200
    assert client.post(f"/api/v1/rectification-orders/{rect['id']}/complete",headers=w,json={"target_status":"待复查","resolution":"已清理"}).status_code==200
    assert client.post(f"/api/v1/rectification-orders/{rect['id']}/review",headers=m,json={"target_status":"已关闭","note":"复查通过"}).status_code==200

