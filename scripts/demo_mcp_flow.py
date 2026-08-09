"""Run an official MCP ClientSession against the stdio server without Inspector UI."""
from __future__ import annotations
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from api.database import SessionLocal
from api.models import User
from mcp_server.client import inspect_stdio_sync

def main():
    db=SessionLocal()
    try:
        user=db.query(User).filter_by(username="resident_demo").first()
        if not user: raise SystemExit("请先运行 python -m data.seed")
        env=os.environ.copy();env.update({"MCP_DEV_AUTH_ENABLED":"true","MCP_DEV_USER_ID":user.id,"MCP_DEV_WRITE_CONFIRMED":"false"})
        result=inspect_stdio_sync(env=env,call=("get_bound_property",{}))
        print("发现工具:",", ".join(x["name"] for x in result["tools"]))
        print("只读调用:",result["call"])
        print("写工具默认被确认策略阻止；将 MCP_DEV_WRITE_CONFIRMED=true 仅用于隔离开发演示。")
    finally: db.close()
if __name__=="__main__":main()
