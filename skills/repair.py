from __future__ import annotations
import re

CATEGORY_RULES={
    "电梯":("电梯",),"给排水":("漏水","渗水","水管","下水"),"公共照明":("灯","照明"),
    "门禁":("门禁","门锁","刷卡"),"消防设施":("消防","灭火器","烟感"),"停车":("车位","停车","车库"),
    "供配电":("跳闸","插座","电箱","配电"),"其他":(),
}
def extract(text: str) -> dict[str,str]:
    category=next((key for key,words in CATEGORY_RULES.items() if any(word in text for word in words)),"其他")
    values={"original_description":text,"fault_description":text,"category":category,"summary":f"{category}报修"}
    building=re.search(r"(\d+)号楼",text); unit=re.search(r"(\d+)单元",text); room=re.search(r"(?:房|室)(\d{2,4})",text)
    if building: values["building_no"]=building.group(1)
    if unit: values["unit_no"]=unit.group(1)
    if room: values["room_no"]=room.group(1)
    location=re.search(r"(?:\d+号楼(?:\d+单元)?[^，。；、\s]{0,30}|楼道|地下车库|电梯内?|门口|公共区域|家里|室内)",text)
    if location: values["location_description"]=location.group(0)
    if "老人" in text or "夜间" in text: values["impact_scope"]="影响通行"
    else: values["impact_scope"]="single"
    values["priority"]="P2" if values.get("impact_scope")=="影响通行" else "P3"
    values["risk_level"]="medium" if values.get("impact_scope")=="影响通行" else "low"
    return values
