"""Official MCP Python SDK server.  It is an adapter over Harness, not a service clone."""
from __future__ import annotations
import os
from typing import Any
from mcp.server.fastmcp import FastMCP
from api.config import settings
from api.database import SessionLocal
from api.models import User
from harness.service import ExecutionContext, ToolResult, get_harness

def _dev_context() -> ExecutionContext:
    if settings.app_env.lower() in {"production","prod"} and settings.mcp_dev_auth_enabled:
        raise RuntimeError("生产环境禁止 MCP 开发认证")
    if not settings.mcp_dev_auth_enabled or not settings.mcp_dev_user_id:
        raise RuntimeError("stdio 模式要求 MCP_DEV_AUTH_ENABLED=true 和受控的 MCP_DEV_USER_ID")
    db=SessionLocal()
    try:
        user=db.get(User,settings.mcp_dev_user_id)
        if not user or not user.is_active: raise RuntimeError("MCP_DEV_USER_ID 不是有效用户")
        return ExecutionContext(user_id=user.id,role=user.role,source="mcp_stdio",transport="stdio",environment=settings.app_env,confirmed=settings.mcp_dev_write_confirmed)
    finally: db.close()

def _call(name:str,args:dict[str,Any]) -> ToolResult:
    db=SessionLocal()
    try:
        ctx=_dev_context()
        result=get_harness().execute(db,ctx,name,args,idempotency_key=args.pop("idempotency_key",None),backend="mcp")
        return ToolResult.model_validate(result)
    finally: db.close()

mcp=FastMCP(settings.mcp_server_name, instructions=("智邻管家物业 MCP。身份来自服务器受控认证上下文；"
    "禁止传入 user_id、role 或绕过确认。公告发布、账单修改、退款和减免均未暴露。"), json_response=True)

@mcp.tool()
def get_current_user_context() -> dict: """读取服务器可信认证上下文。"""; return _call("get_current_user_context",{})
@mcp.tool()
def get_resident_profile() -> dict: """读取当前认证用户的脱敏档案。"""; return _call("get_resident_profile",{})
@mcp.tool()
def get_bound_property() -> dict: """读取当前认证用户的绑定房屋。"""; return _call("get_bound_property",{})
@mcp.tool()
def verify_user_permission(resource_type:str,resource_id:str) -> dict: """服务端验证当前身份是否有权访问对象。"""; return _call("verify_user_permission",locals())
@mcp.tool()
def list_work_orders() -> dict: """读取当前身份可见的工单。"""; return _call("list_work_orders",{})
@mcp.tool()
def list_user_work_orders() -> dict: """读取当前身份可见的工单。"""; return _call("list_user_work_orders",{})
@mcp.tool()
def get_work_order(work_order_id:str) -> dict: """读取有权限访问的工单。"""; return _call("get_work_order",{"work_order_id":work_order_id})
@mcp.tool()
def get_property_bill(bill_id:str) -> dict: """读取有权限访问的模拟账单。"""; return _call("get_property_bill",{"bill_id":bill_id})
@mcp.tool()
def list_payment_records(bill_id:str) -> dict: """读取账单支付记录，不执行支付。"""; return _call("list_payment_records",{"bill_id":bill_id})
@mcp.tool()
def compare_bills(current_bill_id:str,previous_bill_id:str) -> dict: """比较两张有权限访问的账单。"""; return _call("compare_bills",locals())
@mcp.tool()
def list_announcements() -> dict: """读取可见公告。"""; return _call("list_announcements",{})
@mcp.tool()
def get_announcement(announcement_id:str) -> dict: """读取公告详情。"""; return _call("get_announcement",locals())
@mcp.tool()
def get_rectification_status() -> dict: """读取非居民可见的整改状态。"""; return _call("get_rectification_status",{})
@mcp.tool()
def query_knowledge(query:str) -> dict: """检索受控知识库并返回带来源回答。"""; return _call("query_knowledge",{"query":query})
@mcp.tool()
def search_knowledge(query:str) -> dict: """检索知识证据并返回来源。"""; return _call("search_knowledge",locals())
@mcp.tool()
def ask_knowledge(query:str) -> dict: """基于证据回答并返回引用、警告和回答状态。"""; return _call("ask_knowledge",locals())
@mcp.tool()
def search_public_real_cases(query:str|None=None,category:str|None=None,record_kind:str|None=None,limit:int=20) -> dict:
    """仅授权客服/管理员检索脱敏的真实公开住宅维护与巡检整改历史案例；绝不创建或修改记录。"""; return _call("search_public_real_cases",locals())
@mcp.tool()
def create_work_order(property_id:str,summary:str,category:str,location_description:str,fault_description:str,idempotency_key:str) -> dict:
    """创建本人报修：服务端确认已启用的受控工作流才能执行。"""; return _call("create_work_order",locals())
@mcp.tool()
def create_bill_review(bill_id:str,reason:str,idempotency_key:str) -> dict:
    """为本人账单创建核查申请；需要受控确认。"""; return _call("create_bill_review",locals())
@mcp.tool()
def create_bill_review_request(bill_id:str,reason:str,idempotency_key:str) -> dict:
    """为本人账单创建核查申请；需要受控确认。"""; return _call("create_bill_review_request",locals())
@mcp.tool()
def cancel_work_order(work_order_id:str,idempotency_key:str) -> dict:
    """取消本人可取消的工单；需要受控确认。"""; return _call("cancel_work_order",locals())
@mcp.tool()
def rate_work_order(work_order_id:str,score:int,comment:str|None=None,idempotency_key:str="") -> dict:
    """评价本人已完成的工单；需要受控确认。"""; return _call("rate_work_order",locals())
@mcp.tool()
def submit_work_order_rating(work_order_id:str,score:int,comment:str|None=None,idempotency_key:str="") -> dict:
    """评价本人已完成的工单；需要受控确认。"""; return _call("submit_work_order_rating",locals())
@mcp.tool()
def create_announcement_draft(title:str,content:str,affected_scope:str,idempotency_key:str) -> dict:
    """创建公告草稿，绝不发布；需要受控确认。"""; return _call("create_announcement_draft",locals())
@mcp.tool()
def submit_announcement_for_review(announcement_id:str,idempotency_key:str) -> dict:
    """提交公告进入人工审核，绝不直接发布；需要受控确认。"""; return _call("submit_announcement_for_review",locals())
@mcp.tool()
def create_inspection_task(area_type:str,location_description:str,scheduled_at:str,assignee_id:str,idempotency_key:str) -> dict:
    """管理员创建巡检任务；需要受控确认。"""; return _call("create_inspection_task",locals())
@mcp.tool()
def submit_inspection_record(task_id:str,description:str,abnormal:bool=True,risk_level:str="medium",idempotency_key:str="") -> dict:
    """提交本人获分派的巡检记录；需要受控确认。"""; return _call("submit_inspection_record",locals())
@mcp.tool()
def create_rectification(inspection_record_id:str,description:str,risk_level:str="medium",idempotency_key:str="") -> dict:
    """创建整改工单；高风险仅管理员可执行，且需要确认。"""; return _call("create_rectification",locals())
@mcp.tool()
def create_rectification_order(inspection_record_id:str,description:str,risk_level:str="medium",idempotency_key:str="") -> dict:
    """创建整改工单；高风险仅管理员可执行，且需要确认。"""; return _call("create_rectification_order",locals())

def main():
    if not settings.mcp_enabled: raise RuntimeError("MCP_ENABLED=false")
    _dev_context()  # fail fast rather than expose an unauthenticated stdio process
    mcp.run(transport=settings.mcp_transport)

if __name__=="__main__": main()
