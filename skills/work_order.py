from __future__ import annotations
def priority_for(category: str, risk_level: str, impact_scope: str) -> str:
    if risk_level in {"high","critical"}: return "P1"
    if category in {"电梯","消防设施","供配电"} or impact_scope!="single": return "P2"
    return "P3"
