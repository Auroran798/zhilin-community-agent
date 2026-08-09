"""Real stdio protocol verification using the official ClientSession."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.database import Base
from api.models import User, Property, Binding, ExecutionTrace
from api.security import hash_password
from mcp_server.client import inspect_stdio_sync

def test_official_client_lists_and_calls_stdio_server(tmp_path):
    path=tmp_path/"protocol.db";engine=create_engine(f"sqlite:///{path}");Base.metadata.create_all(engine);S=sessionmaker(bind=engine);db=S()
    user=User(username="mcp",password_hash=hash_password("x"),display_name="MCP居民",role="resident");p=Property(community_name="MCP小区",building_no="1",unit_no="1",room_no="101",floor=1)
    db.add_all([user,p]);db.flush();db.add(Binding(user_id=user.id,property_id=p.id));db.commit()
    env=os.environ.copy();env.update({"DATABASE_URL":f"sqlite:///{path}","MCP_DEV_AUTH_ENABLED":"true","MCP_DEV_USER_ID":user.id,"MCP_DEV_WRITE_CONFIRMED":"false"})
    result=inspect_stdio_sync(env=env,call=("get_bound_property",{}))
    assert "create_work_order" in {x["name"] for x in result["tools"]}
    assert result["call"]["isError"] is False and "MCP小区" in result["call"]["content"][0]
    db.expire_all();assert db.query(ExecutionTrace).count()==1
