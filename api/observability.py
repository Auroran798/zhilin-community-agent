"""Local Stage 4 trace inspection.  Only managers can inspect cross-user traces."""
from __future__ import annotations
from statistics import median
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .models import ExecutionTrace, ExecutionSpan, HarnessExecution, AuditLog, User
from .security import require_roles
from api.config import settings
from harness.service import get_harness

router=APIRouter(prefix="/api/v1/observability",tags=["observability"])
mcp_router=APIRouter(prefix="/api/v1/mcp",tags=["mcp"])
def _row(x): return {c.name:getattr(x,c.name) for c in x.__table__.columns}
def _ok(data): return {"success":True,"data":data,"message":"操作成功"}

@router.get("/traces")
def traces(limit:int=100,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
    return _ok({"items":[_row(x) for x in db.query(ExecutionTrace).order_by(ExecutionTrace.created_at.desc()).limit(min(max(limit,1),500))]})

@router.get("/traces/{trace_id}")
def trace(trace_id:str,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
    item=db.query(ExecutionTrace).filter_by(trace_id=trace_id).first()
    if not item: raise HTTPException(404,"调用链不存在")
    return _ok({"trace":_row(item),"spans":[_row(x) for x in db.query(ExecutionSpan).filter_by(trace_id=trace_id).order_by(ExecutionSpan.started_at)],"executions":[_row(x) for x in db.query(HarnessExecution).filter_by(trace_id=trace_id).order_by(HarnessExecution.created_at)]})

@router.get("/metrics")
def metrics(user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
    rows=db.query(HarnessExecution).all(); values=[x.latency_ms for x in rows if x.latency_ms is not None]
    ordered=sorted(values);p95=ordered[max(0,int(len(ordered)*.95)-1)] if ordered else None
    failed=sum(x.status!="completed" for x in rows)
    by_tool={}
    for x in rows: by_tool.setdefault(x.tool_name,{"count":0,"failed":0,"latencies":[]});v=by_tool[x.tool_name];v["count"]+=1;v["failed"]+=x.status!="completed";v["latencies"].append(x.latency_ms or 0)
    return _ok({"sample_size":len(rows),"failure_count":failed,"p50_ms":int(median(values)) if values else None,"p95_ms":p95,"by_tool":{k:{"count":v["count"],"failed":v["failed"],"average_ms":int(sum(v["latencies"])/len(v["latencies"]))} for k,v in by_tool.items()}})

@router.get("/tool-calls")
def tool_calls(limit:int=100,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
    return _ok({"items":[_row(x) for x in db.query(HarnessExecution).order_by(HarnessExecution.created_at.desc()).limit(min(max(limit,1),500))]})

@router.get("/tool-calls/{tool_call_id}")
def tool_call(tool_call_id:str,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
    item=db.get(HarnessExecution,tool_call_id)
    if not item: raise HTTPException(404,"工具调用不存在")
    return _ok(_row(item))

@router.get("/security-events")
def security_events(limit:int=100,user:User=Depends(require_roles("manager")),db:Session=Depends(get_db)):
    q=db.query(AuditLog).filter((AuditLog.result!="success")|(AuditLog.action.like("%security%"))).order_by(AuditLog.created_at.desc())
    return _ok({"items":[_row(x) for x in q.limit(min(max(limit,1),500))]})

@router.get("/mcp/tools")
def mcp_tools(user:User=Depends(require_roles("manager"))):
    # Management discovery must match the actual MCP surface and must not
    # advertise internal-only tools such as ``agent_read``.
    items = [x for x in get_harness().discover() if x.enabled and x.mcp_exposed]
    catalog=[]
    for x in items:
        item=x.model_dump(exclude={"input_model","output_model"})
        item["input_model"]=x.input_model.__name__ if x.input_model else None
        item["output_model"]=x.output_model.__name__ if x.output_model else None
        catalog.append(item)
    return _ok({"items":catalog})

@router.get("/mcp/status")
def mcp_status(user:User=Depends(require_roles("manager"))):
    return _ok({"enabled":settings.mcp_enabled,"transport":settings.mcp_transport,"server_name":settings.mcp_server_name,"client_enabled":settings.mcp_client_enabled,"backend":settings.agent_tool_backend})

@mcp_router.get("/tools")
def mcp_tools_public(user:User=Depends(require_roles("manager"))): return mcp_tools(user)

@mcp_router.get("/status")
def mcp_status_public(user:User=Depends(require_roles("manager"))): return mcp_status(user)
