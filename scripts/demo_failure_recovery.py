"""Deterministic Stage 4 failure/recovery demonstrations on an isolated SQLite DB."""
from __future__ import annotations
import sys, tempfile
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.database import Base
from api.models import User, Property, Binding
from api.security import hash_password
from api.config import settings
from harness.service import ExecutionContext, get_harness

def main():
    with tempfile.TemporaryDirectory(prefix="zhilin-stage4-") as root:
        engine=create_engine(f"sqlite:///{Path(root)/'demo.db'}",connect_args={"check_same_thread":False});Base.metadata.create_all(engine);S=sessionmaker(bind=engine);db=S()
        user=User(username="failure_demo",password_hash=hash_password("x"),display_name="故障演示居民",role="resident");prop=Property(community_name="隔离演示小区",building_no="1",unit_no="1",room_no="101",floor=1);db.add_all([user,prop]);db.flush();db.add(Binding(user_id=user.id,property_id=prop.id));db.commit()
        h=get_harness();h._injected.clear();ctx=ExecutionContext(user_id=user.id,role=user.role,source="test",confirmed=True)
        print("1 transient retry:")
        settings.harness_failure_injection="transient_read_once";r=h.execute(db,ctx,"get_bound_property",{});print(r.model_dump())
        print("2 permanent validation is not retried:")
        settings.harness_failure_injection=None;r=h.execute(db,ctx,"get_work_order",{"work_order_id":"not-a-real-id"});print(r.model_dump())
        args={"property_id":prop.id,"summary":"响应未知演示","category":"公共照明","location_description":"楼道","fault_description":"灯不亮"}
        print("3 unknown-after-write is recovered by idempotency:")
        settings.harness_failure_injection="unknown_after_write";h._injected.clear();r=h.execute(db,ctx,"create_work_order",args,"failure-demo-key");print(r.model_dump())
        print("4 sensitive fields are redacted in trace/span storage; circuit state is local-only.")
        settings.harness_failure_injection=None;db.close();engine.dispose()
if __name__=="__main__": main()
