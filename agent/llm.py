"""Configurable model adapters.  The fake adapter makes tests offline and repeatable."""
from __future__ import annotations
import json
import re
from typing import Any, Protocol, TypeVar
import httpx
from pydantic import BaseModel, ValidationError
from api.config import settings
from .schemas import ExtractedFields, IntentResult
from skills.repair import extract as extract_repair
from skills.announcement import extract as extract_announcement
from skills.inspection import extract as extract_inspection

T = TypeVar("T", bound=BaseModel)

class LLMProvider(Protocol):
    def invoke(self, messages: list[dict[str, str]], **kwargs: Any) -> str: ...
    def invoke_structured(self, messages: list[dict[str, str]], schema: type[T], **kwargs: Any) -> T: ...

def _classify(text: str) -> IntentResult:
    lowered=text.lower()
    rules=[
        (("公开案例","真实公开","公开历史","历史真实案例","真实案例","公共案例","hpd案例"),"public_real_case_query"),
        (("外部工单","上游工单","试点工单","物业系统工单"),"external_work_order_query"),
        (("取消工单","撤销工单","取消我的报修"),"work_order_query"),
        (("整改","整改单"),"rectification_query"),
        (("报修进度","报修状态","报修现在","报修到哪"),"work_order_query"),
        (("报修","坏了","不亮","漏水","故障","修一下"),"repair_request"),
        (("评价工单","给工单打分","满意度","打1分","打2分","打3分","打4分","打5分","评1分","评2分","评3分","评4分","评5分"),"work_order_rating"),
        (("工单","进度","维修到哪"),"work_order_query"),
        (("账单","物业费","缴费","费用"),"bill_review_request" if any(x in text for x in ("核查","不对","争议","复核")) else ("bill_explanation" if any(x in text for x in ("解释","怎么算","明细","为什么","为何","多了","少了","差额")) else "bill_query")),
        (("公告","停水","停电","通知"),"announcement_draft" if any(x in text for x in ("写","生成","草稿","拟")) else "announcement_query"),
        (("巡检","发现隐患","检查记录","积水","滑梯","螺丝松"),"inspection_report"),
        (("设备台账","设备历史","设备查询","设备状态"),"equipment_query"),
        (("人工","客服","投诉"),"human_service"),
        (("规定","可以吗","怎么办","装修","停车","宠物","流程"),"knowledge_question"),
    ]
    for words, intent in rules:
        if any(word in lowered for word in words): return IntentResult(intent=intent, confidence=0.91)
    return IntentResult(intent="out_of_scope", confidence=0.45)

def _extract(text: str) -> ExtractedFields:
    values: dict[str,str]={"original_description":text, "fault_description":text}
    category=next((name for name, words in {"电梯":("电梯",),"给排水":("漏水","下水","水管"),"公共照明":("灯","照明"),"门禁":("门禁","门锁"),"消防设施":("消防",),"停车":("车位","停车")}.items() if any(word in text for word in words)),"其他")
    values["category"]=category;values["summary"]=f"{category}报修"
    location=re.search(r"(?:\d+号楼[^，。；、\s]{0,20}|(?:楼道|地下车库|电梯|门口|公共区域)[^，。；、\s]{0,20})",text)
    if location: values["location_description"]=location.group(0)
    bill_month=re.search(r"20\d{2}[-年]\d{1,2}(?:月)?",text)
    if bill_month: values["billing_period"]=bill_month.group(0)
    title=re.search(r"(?:标题[：:]?|关于)([^，。；\n]{2,40})",text)
    if title: values["title"]=title.group(1).strip()
    elif any(x in text for x in ("公告","通知")): values["title"]="物业服务通知"
    scope=re.search(r"(全体业主|\d+号楼[^，。；\s]{0,12}|全小区)",text)
    if scope: values["affected_scope"]=scope.group(1)
    if any(word in text for word in ("报修","坏了","不亮","漏水","故障","异响")):
        values.update(extract_repair(text))
    if any(word in text for word in ("公告","停水","停电","通知")):
        values.update(extract_announcement(text))
    if any(word in text for word in ("巡检","积水","滑梯","隐患")):
        values.update(extract_inspection(text))
    if "没有人被困" in text or "无人被困" in text or "没人被困" in text: values["is_trapped"]="否"
    elif "有人被困" in text or "困人" in text: values["is_trapped"]="是"
    if "夜间" in text: values.update({"impact_scope":"影响夜间通行","risk_level":"medium","priority":"P2"})
    if any(word in text for word in ("取消工单","撤销工单","取消我的报修")): values["operation"]="cancel"
    score=re.search(r"(?:打|评)[分价]?[：:]?\s*([1-5])\s*分|([1-5])\s*星",text)
    if score: values["score"]=next(x for x in score.groups() if x)
    order=re.search(r"(WO-\d{8}-[A-Z0-9]{4,12})",text,re.I)
    if order: values["work_order_no"]=order.group(1).upper()
    return ExtractedFields(values=values)

class FakeLLMProvider:
    def invoke(self, messages, **kwargs): return "离线 Fake LLM：" + messages[-1]["content"][:100]
    def invoke_structured(self, messages, schema: type[T], **kwargs) -> T:
        text=messages[-1]["content"]
        if schema is IntentResult: return schema.model_validate(_classify(text).model_dump())
        if schema is ExtractedFields: return schema.model_validate(_extract(text).model_dump())
        return schema.model_validate({})

class OpenAICompatibleLLMProvider:
    def __init__(self):
        self.base=(settings.agent_llm_api_base or "").rstrip("/"); self.key=settings.agent_llm_api_key
        if not self.base or not self.key or not settings.agent_llm_model: raise RuntimeError("agent_llm_not_configured")
    def invoke(self,messages,**kwargs):
        response=httpx.post(f"{self.base}/chat/completions",headers={"Authorization":f"Bearer {self.key}"},json={"model":settings.agent_llm_model,"temperature":0,"messages":messages},timeout=settings.agent_llm_timeout_seconds)
        response.raise_for_status()
        payload=response.json(); choices=payload.get("choices") or []
        content=((choices[0].get("message") or {}).get("content") if choices else None)
        if not isinstance(content,str) or not content.strip(): raise RuntimeError("agent_llm_empty_response")
        return content.strip()
    def invoke_structured(self,messages,schema:type[T],**kwargs)->T:
        prompt=[*messages,{"role":"system","content":"仅返回符合 JSON Schema 的对象，不要添加说明。"}]
        last_error=None
        for _ in range(settings.agent_llm_max_retries+1):
            try:
                raw=self.invoke(prompt)
                match=re.search(r"\{.*\}",raw,re.S)
                return schema.model_validate(json.loads(match.group(0) if match else raw))
            except (httpx.HTTPError, json.JSONDecodeError, ValidationError, AttributeError) as exc: last_error=exc
        raise RuntimeError("agent_llm_structured_output_invalid") from last_error

def provider() -> LLMProvider:
    if settings.agent_llm_provider.lower() in {"openai", "openai_compatible"}: return OpenAICompatibleLLMProvider()
    return FakeLLMProvider()
