from __future__ import annotations
import sqlite3
from typing import Any, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.sqlite import SqliteSaver
from api.config import settings
from api.models import AgentStaffReview, Binding, Property, User
from api.services import audit
from skills.registry import get_skill
from .llm import provider
from .schemas import ExtractedFields, IntentResult
from .risk import inspect
from .tools import execute, primary_property, preview, read_tool

class AgentState(TypedDict,total=False):
    session_id:str; request_id:str; run_id:str; user_id:str; user_role:str; property_id:str|None; community:str|None
    current_input:str; normalized_input:str; intent:str; intent_confidence:float; active_skill:str|None; follow_up_rounds:int; continue_previous:bool
    extracted_fields:dict[str,Any]; missing_fields:list[str]; validation_errors:list[str]
    risk_level:str; risk_flags:list[str]; requires_manual_escalation:bool; manual_escalation_reason:str|None; staff_review_id:str|None
    rag_answer_status:str|None; rag_answer:str|None; rag_citations:list[dict]; rag_warnings:list[str]
    proposed_action:str|None; action_preview:dict|None; requires_user_confirmation:bool; confirmation_status:str|None
    tool_name:str|None; tool_result:dict|None; tool_error:str|None; final_answer:str|None; response_status:str

def build_graph(db):
    llm=provider()
    def load_user_context(s):
        u=db.get(User,s["user_id"]); p=primary_property(db,u) if u else None
        return {"user_role":u.role if u else "unknown","property_id":p.id if p else None,"community":p.community_name if p else None}
    def normalize_input(s): return {"normalized_input":" ".join(s["current_input"].split())[:2000]}
    def detect_safety_risk(s):
        level,flags=inspect(s["normalized_input"]); manual=level in {"critical","high"}
        return {"risk_level":level,"risk_flags":flags,"requires_manual_escalation":manual,"manual_escalation_reason":"检测到安全风险或越权指令" if manual else None}
    def route_intent(s):
        if s.get("continue_previous") and s.get("intent") and s.get("missing_fields"):
            return {"intent":s["intent"],"intent_confidence":s.get("intent_confidence",0.9)}
        try:r=llm.invoke_structured([{"role":"user","content":s["normalized_input"]}],IntentResult)
        except Exception:r=IntentResult(intent="human_service",confidence=0)
        manual=s.get("requires_manual_escalation",False) or r.confidence<0.55
        return {"intent":r.intent,"intent_confidence":r.confidence,"requires_manual_escalation":manual,"manual_escalation_reason":s.get("manual_escalation_reason") or ("意图置信度不足" if manual else None)}
    def select_skill(s): return {"active_skill":get_skill(s["intent"]).name}
    def extract_fields(s):
        try:values=llm.invoke_structured([{"role":"user","content":s["normalized_input"]}],ExtractedFields).values
        except Exception:values={}
        # A follow-up only fills or corrects fields from the unfinished turn;
        # it must not discard the resident's original description.
        prior=s.get("extracted_fields",{}) if s.get("continue_previous") else {}
        if prior.get("category") and values.get("category")=="其他":
            values.pop("category",None); values.pop("summary",None)
        values={**prior,**values}
        values["original_description"]=prior.get("original_description",s["normalized_input"])
        if s.get("intent")=="bill_review_request":values["reason"]=s["normalized_input"]
        level=values.get("risk_level") if s.get("risk_level")=="low" else s.get("risk_level")
        return {"extracted_fields":values,"risk_level":level or s.get("risk_level","low")}
    def validate_fields(s):
        spec=get_skill(s["intent"]); fields=s.get("extracted_fields",{})
        missing=[x for x in spec.required_fields if not fields.get(x)]
        # default location must never silently create a work order.
        if s.get("intent")=="repair_request" and fields.get("location_description")=="待补充":missing.append("location_description")
        if s.get("intent")=="repair_request" and fields.get("category")=="电梯" and not fields.get("is_trapped"):missing.append("is_trapped")
        return {"missing_fields":list(dict.fromkeys(missing)),"validation_errors":[]}
    def ask_missing_information(s):
        rounds=s.get("follow_up_rounds",0)+1
        if rounds>settings.agent_max_follow_up_rounds:return {"requires_manual_escalation":True,"manual_escalation_reason":"超过最大补充轮次","follow_up_rounds":rounds}
        labels={"location_description":"具体楼栋、单元和位置","is_trapped":"目前是否有人被困","fault_description":"故障现象"}
        needed="、".join(labels.get(x,x) for x in s["missing_fields"][:2])
        return {"final_answer":f"为继续处理，请补充：{needed}。","response_status":"need_information","follow_up_rounds":rounds}
    def query_rag(s):
        u=db.get(User,s["user_id"]);data=read_tool(db,u,s["intent"],s.get("extracted_fields",{}),s["normalized_input"],s.get("run_id"),s.get("session_id"));result=data["result"]
        if data["tool"]=="query_rag":return {"tool_name":"query_rag","tool_result":result,"rag_answer_status":result.get("answer_status"),"rag_answer":result.get("answer"),"rag_citations":result.get("citations",[]),"rag_warnings":result.get("warnings",[])}
        return {"tool_name":data["tool"],"tool_result":result,"rag_citations":result.get("citations",[]) if isinstance(result,dict) else []}
    def build_action_preview(s):
        u=db.get(User,s["user_id"]);item=preview(db,u,s["intent"],s.get("extracted_fields",{}));return {"action_preview":item,"proposed_action":item.get("action") if item else None,"requires_user_confirmation":bool(item)}
    def request_user_confirmation(s):
        response=interrupt({"type":"confirmation","preview":s["action_preview"],"message":"请确认、修改或取消该操作；未确认前不会写入业务数据。"})
        if not isinstance(response,dict) or response.get("decision")=="cancel":return {"confirmation_status":"cancelled"}
        if response.get("decision")=="modify":
            changed=response.get("fields") or {};return {"action_preview":{**s["action_preview"],**changed},"confirmation_status":"modified"}
        return {"confirmation_status":"confirmed"}
    def execute_business_tool(s):
        if s.get("confirmation_status")!="confirmed":return {"response_status":"cancelled"}
        try:
            u=db.get(User,s["user_id"]);result=execute(db,u,s["action_preview"],f"agent:{s['session_id']}:{s['request_id']}",s.get("run_id"),s.get("session_id"));return {"tool_name":s.get("proposed_action"),"tool_result":result,"response_status":"completed"}
        except Exception as exc:return {"tool_error":str(getattr(exc,"detail",exc)),"response_status":"failed"}
    def request_staff_review(s):
        row=AgentStaffReview(session_id=s["session_id"],user_id=s["user_id"],run_id=s.get("run_id"),reason=s.get("manual_escalation_reason") or "人工服务",review_type="safety" if s.get("risk_level") in {"high","critical"} else "manual_service",summary=s.get("normalized_input",""),risk_level=s.get("risk_level","low"));db.add(row);db.commit();audit(db,db.get(User,s["user_id"]),"agent_manual_review","agent_session",s["session_id"]);db.commit();return {"staff_review_id":row.id,"response_status":"manual_review"}
    def compose_response(s):
        if s.get("response_status")=="need_information":return {}
        if s.get("requires_manual_escalation"):return {"final_answer":"该请求已转交人工物业处理。涉及人身或安全危险时，请立即远离现场并联系紧急服务。","response_status":"manual_review"}
        if s.get("tool_error"):return {"final_answer":f"操作未完成：{s['tool_error']}。","response_status":"failed"}
        if s.get("confirmation_status")=="cancelled":return {"final_answer":"已取消，本次不会创建或修改任何业务记录。","response_status":"cancelled"}
        if s.get("response_status")=="completed":return {"final_answer":"操作已完成。"}
        if s.get("rag_answer") is not None:return {"final_answer":s["rag_answer"],"response_status":s.get("rag_answer_status") or "answered"}
        if s.get("intent")=="bill_explanation" and s.get("tool_result"):
            data=s["tool_result"]
            if data.get("comparison"):
                c=data["comparison"]; detail=f"您本期账单为 {c['current_amount']} 元，上期为 {c['previous_amount']} 元，{c['direction']} {abs(float(c['difference'])):.2f} 元。"
                if data.get("explanation_status")!="explained":detail+=" 当前知识库没有足够收费依据解释差额，您可以提交费用核查申请。"
                else:detail+=" 收费规则依据已在下方来源中展示。"
                return {"final_answer":detail,"response_status":"answered"}
            return {"final_answer":data.get("message","当前无法可靠解释账单差额，可提交费用核查申请。"),"response_status":"answered"}
        if s.get("tool_result") is not None:return {"final_answer":"已查询到相关记录。","response_status":"answered"}
        return {"final_answer":"我可以协助报修、查询工单/账单、制度问答、公告和巡检事项。","response_status":"out_of_scope"}
    def persist_run(s): return {}
    def risk_route(s):return "staff" if s.get("requires_manual_escalation") else "route"
    def after_validate(s):
        if s.get("missing_fields"): return "ask"
        if s.get("intent")=="work_order_query" and s.get("extracted_fields",{}).get("operation")=="cancel": return "preview"
        if s.get("intent")=="work_order_rating" and s.get("extracted_fields",{}).get("score"): return "preview"
        return "read" if s.get("intent") in {"knowledge_question","work_order_query","work_order_rating","external_work_order_query","public_real_case_query","bill_query","bill_explanation","announcement_query","rectification_query","equipment_query"} else "preview"
    def after_ask(s):return "staff" if s.get("requires_manual_escalation") else "compose"
    def after_preview(s):return "confirm" if s.get("requires_user_confirmation") else "compose"
    def after_confirm(s):return "confirm" if s.get("confirmation_status")=="modified" else ("execute" if s.get("confirmation_status")=="confirmed" else "compose")
    g=StateGraph(AgentState)
    for n,f in [("load_user_context",load_user_context),("normalize_input",normalize_input),("detect_safety_risk",detect_safety_risk),("route_intent",route_intent),("select_skill",select_skill),("extract_fields",extract_fields),("validate_fields",validate_fields),("ask_missing_information",ask_missing_information),("query_rag",query_rag),("build_action_preview",build_action_preview),("request_user_confirmation",request_user_confirmation),("execute_business_tool",execute_business_tool),("request_staff_review",request_staff_review),("compose_response",compose_response),("persist_run",persist_run)]:g.add_node(n,f)
    g.add_edge(START,"load_user_context");g.add_edge("load_user_context","normalize_input");g.add_edge("normalize_input","detect_safety_risk");g.add_conditional_edges("detect_safety_risk",risk_route,{"staff":"request_staff_review","route":"route_intent"});g.add_edge("route_intent","select_skill");g.add_edge("select_skill","extract_fields");g.add_edge("extract_fields","validate_fields");g.add_conditional_edges("validate_fields",after_validate,{"ask":"ask_missing_information","read":"query_rag","preview":"build_action_preview"});g.add_conditional_edges("ask_missing_information",after_ask,{"staff":"request_staff_review","compose":"compose_response"});g.add_edge("query_rag","compose_response");g.add_conditional_edges("build_action_preview",after_preview,{"confirm":"request_user_confirmation","compose":"compose_response"});g.add_conditional_edges("request_user_confirmation",after_confirm,{"confirm":"request_user_confirmation","execute":"execute_business_tool","compose":"compose_response"});g.add_edge("execute_business_tool","compose_response");g.add_edge("request_staff_review","compose_response");g.add_edge("compose_response","persist_run");g.add_edge("persist_run",END)
    conn=sqlite3.connect(settings.agent_checkpoint_path,check_same_thread=False); saver=SqliteSaver(conn);saver.setup();return g.compile(checkpointer=saver),conn
