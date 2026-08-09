from __future__ import annotations
import re

INJECTION=("忽略前面", "忽略此前", "系统提示词", "prompt", "api_key", "输出密钥", "越权", "跳过审核", "直接发布", "改成管理员")
RULES={
 "elevator_entrapment":("电梯困人","电梯里.*出不来","被困在电梯"),
 "fire":("着火","火灾","起火","冒烟"),
 "gas_leak":("燃气泄漏","煤气味","燃气味","闻到煤气"),
 "electrical_hazard":("配电箱.*冒烟","焦味","电柜.*水","漏水.*电","积水.*配电","配电.*积水"),
 "injury_or_conflict":("受伤","打架","冲突","流血"),
 "major_loss":("重大损失","责任争议","索赔"),
}

def inspect(text: str) -> tuple[str,list[str]]:
    flags=[]
    lowered=text.lower()
    if any(term in lowered for term in INJECTION): flags.append("prompt_injection_or_privilege_request")
    for flag, patterns in RULES.items():
        if any(re.search(pattern,text,re.I) for pattern in patterns): flags.append(flag)
    if any(f != "prompt_injection_or_privilege_request" for f in flags): return "critical",flags
    return ("high" if flags else "low"),flags
