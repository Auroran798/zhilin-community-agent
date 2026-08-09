from __future__ import annotations
def extract(text: str) -> dict[str,str]:
    risk="high" if any(word in text for word in ("配电","冒烟","焦味","积水")) else "medium" if any(word in text for word in ("堵塞","损坏","故障","破损","松了")) else "low"
    return {"original_description":text,"description":text,"risk_level":risk,"abnormal":"true"}
