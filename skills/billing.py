from __future__ import annotations
from decimal import Decimal
def compare(current: Decimal, previous: Decimal) -> dict[str,str]:
    difference=current-previous
    return {"current_amount":f"{current:.2f}","previous_amount":f"{previous:.2f}","difference":f"{difference:.2f}","direction":"增加" if difference>0 else "减少" if difference<0 else "无变化"}
