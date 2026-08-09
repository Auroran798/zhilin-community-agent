"""Agent gateway selection.  Both routes retain Harness semantics."""
from __future__ import annotations
from typing import Any
import os
from sqlalchemy.orm import Session
from harness.service import ExecutionContext, ToolResult, get_harness

class LocalToolGateway:
    def execute(self,db:Session,ctx:ExecutionContext,name:str,args:dict[str,Any],key:str|None=None)->ToolResult:
        return get_harness().execute(db,ctx,name,args,key,backend="local")

class MCPToolGateway:
    """Network MCP is deliberately opt-in; the server runs the same Harness."""
    def execute(self,db:Session,ctx:ExecutionContext,name:str,args:dict[str,Any],key:str|None=None)->ToolResult:
        from api.config import settings
        if not settings.mcp_client_enabled:
            return ToolResult(ok=False,error={"code":"MCP_CLIENT_DISABLED","message":"MCP 客户端未启用"})
        try:
            from mcp_server.client import call_stdio_sync
            env=os.environ.copy();env.update({"MCP_DEV_AUTH_ENABLED":"true","MCP_DEV_USER_ID":ctx.user_id,
                "MCP_DEV_WRITE_CONFIRMED":"true" if ctx.confirmed else "false"})
            raw=call_stdio_sync(name,{**args,**({"idempotency_key":key} if key else {})},settings.mcp_client_command,env)
            return ToolResult.model_validate(raw)
        except Exception as exc:
            if settings.mcp_allow_local_fallback:
                result=get_harness().execute(db,ctx,name,args,key,backend="local_fallback")
                result.data["degraded_from_mcp"]=True
                return result
            return ToolResult(ok=False,error={"code":"MCP_UNAVAILABLE","message":"MCP 工具不可用，未静默降级"})

def gateway():
    from api.config import settings
    return MCPToolGateway() if settings.agent_tool_backend=="mcp" else LocalToolGateway()
