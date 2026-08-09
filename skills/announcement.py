from __future__ import annotations
import re
def extract(text: str) -> dict[str,str]:
    kind=next((value for term,value in {"停水":"water","停电":"power","电梯":"elevator","消防":"fire","施工":"construction"}.items() if term in text),"notice")
    title=next((f"{term}通知" for term in ("停水","停电","电梯检修","消防演练","道路施工") if term in text),"")
    values={"original_description":text,"announcement_type":kind}
    if title: values["title"]=title
    scope=re.search(r"(?:\d+号楼(?:和|、|,|，)?\d*号楼?|全体业主|全小区|Demo Garden)",text)
    if scope: values["affected_scope"]=scope.group(0)
    time_range=re.search(r"((?:明天|今日|今天)?(?:上午|下午|晚)?\s*\d{1,2}(?::\d{2})?)\s*(?:到|至|—|-)\s*((?:上午|下午|晚)?\s*\d{1,2}(?::\d{2})?)",text)
    if time_range:
        values["start_time"]=time_range.group(1).replace(" ","")
        values["end_time"]=time_range.group(2).replace(" ","")
    reason=re.search(r"(?:原因是|因|由于)([^，。；]{2,80})",text)
    if reason: values["reason"]=reason.group(1)
    return values

def draft(fields: dict[str,str]) -> dict[str,str]:
    title=fields.get("title","物业服务通知")
    scope=fields.get("affected_scope","相关业主")
    reason=fields.get("reason") or fields.get("original_description","")
    period=""
    if fields.get("start_time") and fields.get("end_time"): period=f"计划于{fields['start_time']}至{fields['end_time']}期间"
    formal=f"{title}\n\n因{reason}，{period}影响{scope}相关服务。请相关业主提前做好安排，如有疑问请联系物业服务中心。"
    short=f"【{title}】{period}{scope}因{reason}受影响，请提前做好安排。"
    return {"formal_content":formal,"group_content":short}
