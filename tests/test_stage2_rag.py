from fastapi.testclient import TestClient
from api.main import app
from api.database import Base, get_db
from api.models import User, Property, Binding, Announcement, KnowledgeDocument, OutboxEvent
from api.security import hash_password
from api.outbox import process_pending
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_rag_ingest_and_resident_scope(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'rag.db'}",connect_args={"check_same_thread":False}); Base.metadata.create_all(engine); Session=sessionmaker(bind=engine)
    db=Session(); manager=User(username="manager",password_hash=hash_password("x"),display_name="M",role="manager"); resident=User(username="resident",password_hash=hash_password("x"),display_name="R",role="resident"); prop=Property(community_name="Demo Garden",building_no="1",unit_no="1",room_no="101",floor=1)
    db.add_all([manager,resident,prop]);db.flush();db.add(Binding(user_id=resident.id,property_id=prop.id));db.commit()
    def override():
        session=Session()
        try: yield session
        finally: session.close()
    app.dependency_overrides[get_db]=override; client=TestClient(app)
    def token(name): return client.post('/api/v1/auth/login',json={'username':name,'password':'x'}).json()['data']['access_token']
    headers={'Authorization':'Bearer '+token('manager')}
    upload=client.post('/api/v1/knowledge/documents',headers=headers,data={'title':'装修规定','applicable_community':'Demo Garden'},files={'file':('rule.md','# 装修\n周末不得进行产生噪声的装修。','text/markdown')})
    assert upload.status_code==200
    doc=upload.json()['data']; assert client.post(f"/api/v1/knowledge/documents/{doc['id']}/index",headers=headers).status_code==200
    resident_headers={'Authorization':'Bearer '+token('resident')}
    result=client.post('/api/v1/knowledge/query',headers=resident_headers,data={'query':'周末可以装修吗'}).json()['data']
    assert result['answer_status']=='answered' and result['citations']
    assert client.post('/api/v1/knowledge/query',headers=resident_headers,data={'query':'今晚八点一定修好电梯吗'}).json()['data']['answer_status']=='refused'
    app.dependency_overrides.clear();db.close()

def test_only_published_announcement_is_indexed(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'notice.db'}",connect_args={"check_same_thread":False}); Base.metadata.create_all(engine); Session=sessionmaker(bind=engine)
    db=Session(); manager=User(username="manager2",password_hash=hash_password("x"),display_name="M",role="manager"); service=User(username="service2",password_hash=hash_password("x"),display_name="S",role="customer_service")
    db.add_all([manager,service]);db.commit()
    def override():
        session=Session()
        try: yield session
        finally: session.close()
    app.dependency_overrides[get_db]=override; client=TestClient(app)
    def header(name): return {'Authorization':'Bearer '+client.post('/api/v1/auth/login',json={'username':name,'password':'x'}).json()['data']['access_token']}
    draft=client.post('/api/v1/announcements',headers=header('service2'),json={'title':'停水公告','announcement_type':'water','content':'明日停水。','affected_scope':'Demo Garden','contact_information':'物业'}).json()['data']
    assert db.query(KnowledgeDocument).filter_by(source_business_id=draft['id']).count()==0
    assert client.post(f"/api/v1/announcements/{draft['id']}/submit-review",headers=header('service2')).status_code==200
    assert client.post(f"/api/v1/announcements/{draft['id']}/approve",headers=header('manager2')).status_code==200
    assert client.post(f"/api/v1/announcements/{draft['id']}/publish",headers=header('manager2')).status_code==200
    assert process_pending(db)['processed']==1
    assert db.query(KnowledgeDocument).filter_by(source_business_type='announcement',source_business_id=draft['id']).first().status=='active'
    assert client.post(f"/api/v1/announcements/{draft['id']}/withdraw",headers=header('manager2')).status_code==200
    assert process_pending(db)['processed']==1
    assert db.query(KnowledgeDocument).filter_by(source_business_type='announcement',source_business_id=draft['id']).first().status=='inactive'
    app.dependency_overrides.clear();db.close()

def test_index_failure_does_not_undo_published_announcement(tmp_path,monkeypatch):
    engine=create_engine(f"sqlite:///{tmp_path/'outbox-failure.db'}",connect_args={"check_same_thread":False});Base.metadata.create_all(engine);Session=sessionmaker(bind=engine)
    db=Session();manager=User(username="outbox-manager",password_hash=hash_password("x"),display_name="M",role="manager");service=User(username="outbox-service",password_hash=hash_password("x"),display_name="S",role="customer_service");db.add_all([manager,service]);db.commit()
    announcement=Announcement(title="索引故障测试",announcement_type="notice",content="业务发布不能回滚。",affected_scope="Demo Garden",contact_information="物业",publisher_unit="物业",status="approved",created_by=service.id,reviewed_by=manager.id);db.add(announcement);db.commit()
    from api.stage7 import AnnouncementService
    AnnouncementService.publish(db,manager,announcement)
    assert announcement.status=="published" and db.query(OutboxEvent).filter_by(aggregate_id=announcement.id,status="pending").count()==1
    monkeypatch.setattr("rag.service.sync_published_announcement",lambda *_args,**_kwargs: (_ for _ in ()).throw(RuntimeError("vector unavailable")))
    result=process_pending(db)
    db.refresh(announcement);event=db.query(OutboxEvent).filter_by(aggregate_id=announcement.id).one()
    assert result=={"processed":0,"failed":1}
    assert announcement.status=="published" and event.status=="retry" and "vector unavailable" in event.last_error
    db.close()
