from __future__ import annotations
import json,re,time,uuid
from datetime import timedelta
from fastapi import HTTPException
from langgraph.types import Command
from api.config import settings
from api.models import AgentConfirmation,AgentMemory,AgentMessage,AgentRun,AgentSession,AgentStaffReview,Binding,Property,User
from api.services import audit
from api.time import as_utc, utc_now
from api.idempotency import fingerprint
from .graph import build_graph

def _safe(v):return json.dumps(v,ensure_ascii=False,default=str)
def _redact(text:str):return re.sub(r"(?<!\d)1\d{10}(?!\d)","***",text)[:4000]
def record_message(db,sid,role,content,metadata=None):
    row=AgentMessage(session_id=sid,role=role,content=content[:4000],content_redacted=_redact(content),metadata_json=_safe(metadata) if metadata else None);db.add(row);db.commit();return row

class AgentService:
    def create_session(self,db,user,product_mode="domestic_beijing",jurisdiction=None):
        p=(db.query(Binding).filter_by(user_id=user.id,is_primary=True).first() or db.query(Binding).filter_by(user_id=user.id).first());prop=db.get(Property,p.property_id) if p else None
        item=AgentSession(user_id=user.id,property_id=prop.id if prop else None,community_name=prop.community_name if prop else None,product_mode=product_mode,jurisdiction=jurisdiction);db.add(item);db.commit();return item
    def sessions(self,db,user):return db.query(AgentSession).filter_by(user_id=user.id).order_by(AgentSession.updated_at.desc()).all()
    def owned_session(self,db,user,sid):
        item=db.get(AgentSession,sid)
        if not item or item.user_id!=user.id:raise HTTPException(404,"会话不存在")
        return item
    def messages(self,db,user,sid):self.owned_session(db,user,sid);return db.query(AgentMessage).filter_by(session_id=sid).order_by(AgentMessage.created_at).all()
    def _run(self,db,session,request_id):
        r=AgentRun(session_id=session.id,request_id=request_id,status="running",llm_provider=settings.agent_llm_provider,llm_model=settings.agent_llm_model);db.add(r);db.commit();return r
    def _finish(self,db,run,result,status,started):
        run.intent=result.get("intent");run.intent_confidence=result.get("intent_confidence");run.active_skill=result.get("active_skill");run.status=status;run.risk_level=result.get("risk_level","low");run.requires_manual_escalation=result.get("requires_manual_escalation",False);run.tool_name=result.get("tool_name");run.error_code=(result.get("tool_error") or "")[:64] or None;run.summary_json=_safe({"risk_flags":result.get("risk_flags",[]),"missing_fields":result.get("missing_fields",[])});run.latency_ms=int((time.perf_counter()-started)*1000);run.finished_at=utc_now();db.commit()
    def _payload(self,result,status,confirmation=None):
        action_preview=result.get("action_preview")
        return {"session_id":result.get("session_id"),"run_id":result.get("run_id"),"status":status,"product_mode":result.get("product_mode","domestic_beijing"),"jurisdiction":result.get("jurisdiction"),"intent":result.get("intent"),"intent_confidence":result.get("intent_confidence"),"active_skill":result.get("active_skill"),"tool_name":result.get("tool_name"),"answer":result.get("final_answer"),"extracted_fields":result.get("extracted_fields",{}),"missing_fields":result.get("missing_fields",[]),"risk_level":result.get("risk_level","low"),"risk_flags":result.get("risk_flags",[]),"citations":result.get("rag_citations",[]),"tool_result":result.get("tool_result"),"action_preview":action_preview,"preview":action_preview,"confirmation_id":confirmation.id if confirmation else None,"staff_review_id":result.get("staff_review_id")}
    def turn(self,db,user,sid,content,product_mode=None,jurisdiction=None):
        if not settings.agent_enabled:raise HTTPException(503,"智能体功能未启用")
        session=self.owned_session(db,user,sid)
        if session.status=="cancelled":raise HTTPException(409,"会话已取消，请创建新会话")
        text=" ".join(content.split())[:2000]
        if not text:raise HTTPException(400,"消息不能为空")
        mode=product_mode or session.product_mode or settings.product_mode
        if mode not in {"domestic_beijing","international_research","demo_garden"}:raise HTTPException(400,"无效产品模式")
        session.product_mode=mode;session.jurisdiction=jurisdiction or session.jurisdiction
        record_message(db,sid,"user",text,{"product_mode":mode,"jurisdiction":session.jurisdiction});rid=str(uuid.uuid4());run=self._run(db,session,rid);graph,conn=build_graph(db);started=time.perf_counter()
        initial={"session_id":sid,"request_id":rid,"run_id":run.id,"user_id":user.id,"user_role":user.role,"product_mode":mode,"jurisdiction":session.jurisdiction,"current_input":text,"response_status":"running","follow_up_rounds":session.follow_up_rounds,"continue_previous":session.follow_up_rounds>0,"rag_citations":[],"tool_result":None,"tool_error":None,"action_preview":None,"proposed_action":None,"confirmation_status":None,"requires_manual_escalation":False,"risk_flags":[]}
        try:result=graph.invoke(initial,config={"configurable":{"thread_id":session.thread_id}})
        finally:conn.close()
        interrupted="__interrupt__" in result; confirmation=None
        if interrupted and result.get("action_preview"):
            preview=_safe(result["action_preview"]);confirmation=AgentConfirmation(session_id=sid,run_id=run.id,user_id=user.id,action=result["action_preview"]["action"],action_type=result["action_preview"]["action"],preview_json=preview,payload_hash=fingerprint(preview),idempotency_key=f"agent:{sid}:{rid}",expires_at=utc_now()+timedelta(minutes=settings.agent_confirmation_ttl_minutes));db.add(confirmation);db.commit();result["final_answer"]="已生成操作预览，请确认、修改或取消。";status="awaiting_confirmation"
        else:status=result.get("response_status","answered")
        session.current_intent=result.get("intent");session.current_skill=result.get("active_skill");session.follow_up_rounds=result.get("follow_up_rounds",0) if status=="need_information" else 0;db.commit();self._finish(db,run,result,status,started)
        record_message(db,sid,"assistant",result.get("final_answer") or "请求已受理。",{"status":status,"run_id":run.id,"product_mode":mode,"jurisdiction":result.get("jurisdiction")});return self._payload(result,status,confirmation)
    def confirmation(self,db,user,cid):
        item=db.get(AgentConfirmation,cid)
        if not item or item.user_id!=user.id:raise HTTPException(404,"确认请求不存在")
        return item
    def _resume(self,db,item,payload):
        graph,conn=build_graph(db)
        try:return graph.invoke(Command(resume=payload),config={"configurable":{"thread_id":self.owned_session(db,db.get(User,item.user_id),item.session_id).thread_id}})
        except Exception as exc:raise HTTPException(409,"会话状态无法恢复，请重新发起请求") from exc
        finally:conn.close()
    def confirm(self,db,user,cid):
        item=self.confirmation(db,user,cid)
        if item.status=="completed":return {"status":"completed","result":json.loads(item.result_json or "{}"),"idempotent":True}
        if item.status!="pending":raise HTTPException(409,"确认请求正在处理或已处理")
        if as_utc(item.expires_at)<=utc_now():item.status="expired";db.commit();raise HTTPException(409,"确认请求已失效")
        if item.payload_hash and fingerprint(item.preview_json)!=item.payload_hash:
            item.status="failed";db.commit();raise HTTPException(409,"确认预览完整性校验失败")
        claimed=db.query(AgentConfirmation).filter_by(id=cid,user_id=user.id,status="pending").update({"status":"processing","confirmed_at":utc_now()},synchronize_session=False)
        db.commit()
        if claimed!=1:raise HTTPException(409,"确认请求正在处理或已处理")
        item=db.get(AgentConfirmation,cid)
        try:
            result=self._resume(db,item,{"decision":"confirm"});item.status="completed" if result.get("response_status")=="completed" else "failed";item.result_json=_safe(result.get("tool_result") or {"answer":result.get("final_answer")});db.commit();record_message(db,item.session_id,"assistant",result.get("final_answer","操作已处理。"),{"confirmation_id":item.id,"status":item.status});return {"status":item.status,"answer":result.get("final_answer"),"result":result.get("tool_result")}
        except Exception:
            db.rollback();item=db.get(AgentConfirmation,cid);item.status="failed";db.commit();raise
    def cancel_confirmation(self,db,user,cid):
        item=self.confirmation(db,user,cid)
        if item.status=="cancelled":return {"status":"cancelled","idempotent":True}
        if item.status!="pending":raise HTTPException(409,"确认请求已处理")
        claimed=db.query(AgentConfirmation).filter_by(id=cid,user_id=user.id,status="pending").update({"status":"cancelling"},synchronize_session=False);db.commit()
        if claimed!=1:raise HTTPException(409,"确认请求正在处理或已处理")
        item=db.get(AgentConfirmation,cid);result=self._resume(db,item,{"decision":"cancel"});item.status="cancelled";item.cancelled_at=utc_now();item.result_json=_safe({"answer":result.get("final_answer")});db.commit();record_message(db,item.session_id,"assistant",result.get("final_answer","已取消。"),{"confirmation_id":item.id,"status":"cancelled"});return {"status":"cancelled","answer":result.get("final_answer")}
    def modify_confirmation(self,db,user,cid,fields):
        item=self.confirmation(db,user,cid)
        if item.status!="pending":raise HTTPException(409,"确认请求已处理")
        claimed=db.query(AgentConfirmation).filter_by(id=cid,user_id=user.id,status="pending").update({"status":"modifying"},synchronize_session=False);db.commit()
        if claimed!=1:raise HTTPException(409,"确认请求正在处理或已处理")
        item=db.get(AgentConfirmation,cid);result=self._resume(db,item,{"decision":"modify","fields":fields});item.status="modified";item.result_json=_safe({"preview":result.get("action_preview")});db.commit()
        # graph interrupts again on the revised preview; create a successor confirmation.
        preview=_safe(result["action_preview"]);new=AgentConfirmation(session_id=item.session_id,run_id=item.run_id,user_id=user.id,action=result["action_preview"]["action"],action_type=result["action_preview"]["action"],preview_json=preview,payload_hash=fingerprint(preview),idempotency_key=f"{item.id}:modified",expires_at=utc_now()+timedelta(minutes=settings.agent_confirmation_ttl_minutes));db.add(new);db.commit();return {"status":"awaiting_confirmation","confirmation_id":new.id,"preview":result.get("action_preview")}
    def state(self,db,user,sid):
        session=self.owned_session(db,user,sid);latest=db.query(AgentRun).filter_by(session_id=sid).order_by(AgentRun.created_at.desc()).first();return {"session_id":sid,"session_status":session.status,"current_intent":session.current_intent,"current_skill":session.current_skill,"latest_run_id":latest.id if latest else None,"latest_status":latest.status if latest else None}
    def cancel_session(self,db,user,sid):
        s=self.owned_session(db,user,sid);s.status="cancelled";s.closed_at=utc_now();db.commit();return s
    def save_memory(self,db,user,key,value,memory_type,consented):
        if not settings.agent_long_term_memory_enabled:raise HTTPException(503,"长期记忆功能未启用")
        if not consented:raise HTTPException(400,"保存长期记忆需要用户明确同意")
        if any(x in (key+value).lower() for x in ("password","token","身份证","银行卡","验证码")):raise HTTPException(400,"不得保存敏感信息")
        item=db.query(AgentMemory).filter_by(user_id=user.id,memory_key=key).first()
        if item:item.value=value;item.memory_type=memory_type;item.consented=True;item.consented_at=utc_now()
        else:item=AgentMemory(user_id=user.id,memory_key=key,value=value,memory_type=memory_type,consented=True);db.add(item)
        db.commit();audit(db,user,"agent_memory_consent","agent_memory",item.id);db.commit();return item
    def delete_memory(self,db,user,memory_id):
        item=db.query(AgentMemory).filter_by(user_id=user.id,id=memory_id).first() or db.query(AgentMemory).filter_by(user_id=user.id,memory_key=memory_id).first()
        if not item:raise HTTPException(404,"记忆不存在")
        item.deleted_at=utc_now();db.commit();audit(db,user,"agent_memory_delete","agent_memory",item.id);db.commit()
    def reviews(self,db,user):
        if user.role not in {"customer_service","manager"}:raise HTTPException(403,"无权处理人工工单")
        q=db.query(AgentStaffReview);return q.all() if user.role=="manager" else q.filter((AgentStaffReview.assigned_to==None)|(AgentStaffReview.assigned_to==user.id)).all()
    def review(self,db,user,rid):
        x=db.get(AgentStaffReview,rid)
        if not x or (user.role=="customer_service" and x.assigned_to not in {None,user.id}):raise HTTPException(404,"人工处理单不存在")
        return x
    def assign_review(self,db,user,rid,assignee_id):
        if user.role!="manager":raise HTTPException(403,"仅管理员可分派")
        x=self.review(db,user,rid);staff=db.get(User,assignee_id)
        if not staff or staff.role not in {"customer_service","manager"}:raise HTTPException(400,"处理人必须是客服或管理员")
        x.assigned_to=staff.id;x.status="assigned";db.commit();return x
    def resolve_review(self,db,user,rid,result):
        x=self.review(db,user,rid)
        if user.role=="customer_service" and x.assigned_to not in {None,user.id}:raise HTTPException(403,"该人工单未分派给当前人员")
        x.assigned_to=x.assigned_to or user.id;x.status="resolved";x.result=result;x.handled_at=utc_now();db.commit();audit(db,user,"resolve_agent_review","agent_staff_review",x.id);db.commit();return x
