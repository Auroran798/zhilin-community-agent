from fastapi.testclient import TestClient
from api.main import app
client=TestClient(app)
def token(username):
 r=client.post("/api/v1/auth/login",json={"username":username,"password":"DemoPass123!"});assert r.status_code==200;return r.json()["data"]["access_token"]
def h(name):return {"Authorization":"Bearer "+token(name)}
def test_roles_login():
 for name in ["resident_demo","service_demo","maintenance_demo","manager_demo"]:assert client.post("/api/v1/auth/login",json={"username":name,"password":"DemoPass123!"}).status_code==200
def test_resident_visibility_and_idempotency():
 headers=h("resident_demo");props=client.get("/api/v1/properties/my",headers=headers).json()["data"];assert props
 data={"property_id":props[0]["id"],"original_description":"楼道灯不亮","summary":"照明故障","category":"公共照明","location_description":"1号楼","fault_description":"灯不亮"}
 a=client.post("/api/v1/work-orders",headers={**headers,"Idempotency-Key":"pytest-wo-1"},json=data);b=client.post("/api/v1/work-orders",headers={**headers,"Idempotency-Key":"pytest-wo-1"},json=data)
 assert a.status_code==200 and a.json()["data"]["id"]==b.json()["data"]["id"]

def test_idempotency_is_scoped_to_actor_and_payload():
 first=h("resident_demo");second=h("resident_001")
 first_property=client.get("/api/v1/properties/my",headers=first).json()["data"][0]
 second_property=client.get("/api/v1/properties/my",headers=second).json()["data"][0]
 def payload(prop,summary):return {"property_id":prop["id"],"original_description":summary,"summary":summary,"category":"公共照明","location_description":"楼道","fault_description":summary}
 key="same-client-key-across-two-residents"
 one=client.post("/api/v1/work-orders",headers={**first,"Idempotency-Key":key},json=payload(first_property,"一号楼照明故障"))
 two=client.post("/api/v1/work-orders",headers={**second,"Idempotency-Key":key},json=payload(second_property,"二号楼照明故障"))
 assert one.status_code==two.status_code==200
 assert one.json()["data"]["id"]!=two.json()["data"]["id"]
 conflict=client.post("/api/v1/work-orders",headers={**first,"Idempotency-Key":key},json=payload(first_property,"同键但修改后的故障"))
 assert conflict.status_code==409
def test_announcement_needs_approval():
 service=h("service_demo");manager=h("manager_demo")
 data={"title":"测试公告","announcement_type":"notice","content":"模拟内容","affected_scope":"1号楼","contact_information":"物业服务中心"}
 a=client.post("/api/v1/announcements",headers=service,json=data).json()["data"]
 assert client.post(f"/api/v1/announcements/{a['id']}/submit-review",headers=service).status_code==200
 assert client.post(f"/api/v1/announcements/{a['id']}/publish",headers=service).status_code==403
 assert client.post(f"/api/v1/announcements/{a['id']}/approve",headers=manager).status_code==200
 assert client.post(f"/api/v1/announcements/{a['id']}/publish",headers=manager).status_code==200
