"""Official ClientSession adapter used by tests and the optional Agent MCP gateway."""
from __future__ import annotations
import asyncio, json, sys
from typing import Any
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from api.config import settings

async def inspect_stdio(command:str|None=None, env:dict[str,str]|None=None, call:tuple[str,dict]|None=None)->dict[str,Any]:
    params=StdioServerParameters(command=command or sys.executable,args=["-m","mcp_server.server"],env=env)
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize(); tools=await session.list_tools()
            result={"tools":[{"name":x.name,"description":x.description,"inputSchema":x.inputSchema} for x in tools.tools]}
            if call:
                response=await session.call_tool(call[0],call[1]);result["call"]={"isError":response.isError,"content":[getattr(x,"text",str(x)) for x in response.content]}
            return result

def inspect_stdio_sync(**kwargs): return asyncio.run(inspect_stdio(**kwargs))

def call_stdio_sync(name:str,args:dict[str,Any],command:str|None=None,env:dict[str,str]|None=None)->dict[str,Any]:
    response=inspect_stdio_sync(command=command,env=env,call=(name,args))["call"]
    if response["isError"]: return {"ok":False,"error":{"code":"MCP_PROTOCOL_ERROR","message":"; ".join(response["content"])}}
    try: return json.loads(response["content"][0])
    except (IndexError,json.JSONDecodeError): return {"ok":False,"error":{"code":"MCP_PROTOCOL_ERROR","message":"MCP 返回了不可解析内容"}}
