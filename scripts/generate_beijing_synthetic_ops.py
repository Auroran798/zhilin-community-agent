"""Generate deterministic, non-personal Beijing property-operation demo data."""
from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"data"/"demo_synthetic"/"beijing_property_ops_6000.jsonl"
MANIFEST=ROOT/"data"/"demo_synthetic"/"manifest.json"
OPS_PUBLIC=ROOT/"data"/"ops_public"/"beijing_12345_2022_metadata.json"
SEED=20260810
START=datetime(2025,2,1,tzinfo=timezone(timedelta(hours=8)))
END=datetime(2026,8,1,23,59,59,tzinfo=timezone(timedelta(hours=8)))
COUNTS={"work_order":1800,"complaint":700,"inspection_task":900,"inspection_anomaly":300,"rectification":300,"equipment_asset":400,"bill":900,"bill_review":200,"announcement":150,"sla_event":350}
COMMUNITY="北京市合成示范社区（非真实小区）"
ZONES=["A区公共区域","B区公共区域","地下设备区","园区外围","客服中心演示区"]
EQUIPMENT=["电梯","消防设施","二次供水","配电设施","供热设施","燃气共用设施"]
WORK_CATEGORIES=["电梯故障","消防通道","供水报修","供电报修","供热报修","燃气巡查","房屋渗漏","公共照明","环境保洁","噪声协调"]
COMPLAINT_CATEGORIES=["服务响应","收费咨询","公共收益公示","停车秩序","装修管理","噪声协调","宠物管理","垃圾分类"]


def moment(rng:random.Random)->datetime:
    return START+timedelta(seconds=rng.randrange(int((END-START).total_seconds())+1))


def iso(value:datetime)->str:
    return value.isoformat(timespec="seconds")


def base(kind:str,index:int,created:datetime)->dict:
    prefix={"work_order":"WO","complaint":"CP","inspection_task":"IT","inspection_anomaly":"IA","rectification":"RC","equipment_asset":"EA","bill":"BL","bill_review":"BR","announcement":"AN","sla_event":"SL"}[kind]
    return {"record_id":f"SYN-BJ-{prefix}-{index:05d}","record_type":kind,"data_class":"DEMO_SYNTHETIC","synthetic":True,"product_mode":"demo_garden","jurisdiction":"北京市合成示范社区","community":COMMUNITY,"created_at":iso(created)}


def seasonal_work_category(rng:random.Random,created:datetime)->str:
    weighted=list(WORK_CATEGORIES)
    if created.month in {11,12,1,2,3}: weighted+=(["供热报修"]*7+["供水报修"]*2)
    if created.month in {6,7,8}: weighted+=(["房屋渗漏"]*7+["供电报修"]*2)
    return rng.choice(weighted)


def make_work_order(rng,index):
    created=moment(rng);priority=rng.choices(["一般","紧急","重大"],[0.72,0.24,0.04])[0];response_limit={"一般":120,"紧急":30,"重大":10}[priority]
    response_minutes=max(2,int(rng.triangular(3,response_limit*1.5,response_limit*.55)));assigned=created+timedelta(minutes=rng.randint(1,15));responded=created+timedelta(minutes=response_minutes);completed=responded+timedelta(minutes=rng.randint(20,2880));closed=completed+timedelta(hours=rng.randint(2,72))
    row=base("work_order",index,created);row.update({"resident_ref":f"DEMO-R-{rng.randint(1,850):04d}","property_ref":f"DEMO-U-{rng.randint(1,1200):04d}","location_zone":rng.choice(ZONES),"category":seasonal_work_category(rng,created),"priority":priority,"status":"closed","assigned_team":rng.choice(["综合维修演示组","秩序维护演示组","设备运行演示组","客服协调演示组"]),"assigned_at":iso(assigned),"responded_at":iso(responded),"completed_at":iso(completed),"followed_up_at":iso(closed),"sla_response_limit_minutes":response_limit,"sla_response_minutes":response_minutes,"sla_met":response_minutes<=response_limit,"resolution_code":rng.choice(["现场处理完成","计划维修完成","协调第三方完成","用户确认无需继续"]),"rating":rng.choices([1,2,3,4,5],[.01,.03,.10,.34,.52])[0]});return row


def make_complaint(rng,index):
    created=moment(rng);responded=created+timedelta(minutes=rng.randint(8,240));closed=responded+timedelta(hours=rng.randint(2,168));row=base("complaint",index,created);row.update({"resident_ref":f"DEMO-R-{rng.randint(1,850):04d}","category":rng.choice(COMPLAINT_CATEGORIES),"channel":rng.choice(["演示客服台","演示小程序","演示热线"]),"location_zone":rng.choice(ZONES),"status":"closed","responded_at":iso(responded),"completed_at":iso(closed),"requires_government_coordination":rng.random()<.08,"individual_government_case":False,"outcome":"演示闭环，不代表真实投诉处理结果","rating":rng.randint(2,5)});return row


def make_inspection(rng,index):
    created=moment(rng);row=base("inspection_task",index,created);row.update({"equipment_type":rng.choice(EQUIPMENT),"location_zone":rng.choice(ZONES),"frequency":rng.choice(["日检","周检","月检","季度检"]),"assigned_team":"合成巡检组","started_at":iso(created+timedelta(minutes=5)),"completed_at":iso(created+timedelta(minutes=rng.randint(20,180))),"result":rng.choices(["正常","发现一般隐患","发现紧急隐患"],[.84,.14,.02])[0],"checklist_version":"SYN-CHECK-2026.1"});return row


def make_anomaly(rng,index):
    created=moment(rng);row=base("inspection_anomaly",index,created);row.update({"inspection_ref":f"SYN-BJ-IT-{rng.randint(1,900):05d}","equipment_type":rng.choice(EQUIPMENT),"location_zone":rng.choice(ZONES),"severity":rng.choices(["一般","较大","紧急"],[.72,.23,.05])[0],"description":rng.choice(["演示：状态指示异常","演示：例行检查值偏离阈值","演示：通道存在临时占用","演示：维护标识需更新"]),"requires_rectification":True,"reported_to_real_authority":False});return row


def make_rectification(rng,index):
    created=moment(rng);deadline=created+timedelta(days=rng.randint(1,15));finished=deadline-timedelta(hours=rng.randint(0,36));row=base("rectification",index,created);row.update({"anomaly_ref":f"SYN-BJ-IA-{rng.randint(1,300):05d}","owner_team":"合成整改组","deadline":iso(deadline),"completed_at":iso(finished),"verification":"演示复核通过","status":"closed","external_report":False});return row


def make_asset(rng,index):
    created=moment(rng);row=base("equipment_asset",index,created);row.update({"asset_code":f"DEMO-ASSET-{index:04d}","equipment_type":rng.choice(EQUIPMENT),"location_zone":rng.choice(ZONES),"manufacturer":"合成厂商代号（非真实企业）","model":"SYN-MODEL","commissioned_year":rng.randint(2005,2025),"inspection_cycle_days":rng.choice([7,30,90,365]),"next_inspection_at":iso(END+timedelta(days=rng.randint(1,180))),"status":rng.choice(["在用","演示维护中","演示备用"])});return row


def make_bill(rng,index):
    created=moment(rng);period=created.strftime("%Y-%m");area=round(rng.uniform(42,168),2);unit=round(rng.choice([2.35,2.68,3.2,3.6]),2);row=base("bill",index,created);row.update({"bill_no":f"DEMO-BILL-{index:05d}","resident_ref":f"DEMO-R-{rng.randint(1,850):04d}","property_ref":f"DEMO-U-{rng.randint(1,1200):04d}","billing_period":period,"charge_item":"模拟物业服务费","area_sqm":area,"unit_price":unit,"amount":round(area*unit,2),"currency":"CNY","status":rng.choice(["模拟已付","模拟待付","模拟复核中"]),"real_invoice":False});return row


def make_bill_review(rng,index):
    created=moment(rng);row=base("bill_review",index,created);row.update({"bill_ref":f"SYN-BJ-BL-{rng.randint(1,900):05d}","requested_by":f"DEMO-R-{rng.randint(1,850):04d}","reason":rng.choice(["面积参数复核","计费期间复核","收费项目说明","支付状态核对"]),"status":"manual_review_completed","changed_amount":False,"automatic_reduction":False,"result":"合成演示复核记录；未修改真实账单"});return row


def make_announcement(rng,index):
    created=moment(rng);row=base("announcement",index,created);row.update({"title":rng.choice(["合成消防演练通知","合成停水检修提示","合成供暖季巡检提示","合成垃圾分类提示","合成暴雨防范提示"]),"audience":"合成示范社区用户","status":"demo_only","published_to_real_users":False,"requires_explicit_confirmation":True,"content":"DEMO_SYNTHETIC：本通知仅用于流程展示，不对应真实物业、居民或事件。"});return row


def make_sla(rng,index):
    created=moment(rng);stage=rng.choice(["received","assigned","responded","completed","followed_up"]);row=base("sla_event",index,created);row.update({"work_order_ref":f"SYN-BJ-WO-{rng.randint(1,1800):05d}","stage":stage,"event_at":iso(created),"actor_ref":f"DEMO-STAFF-{rng.randint(1,60):03d}","audit_only":True});return row


MAKERS={"work_order":make_work_order,"complaint":make_complaint,"inspection_task":make_inspection,"inspection_anomaly":make_anomaly,"rectification":make_rectification,"equipment_asset":make_asset,"bill":make_bill,"bill_review":make_bill_review,"announcement":make_announcement,"sla_event":make_sla}


def validate(rows:list[dict])->dict:
    errors=[];counts=Counter(row["record_type"] for row in rows);timestamps=[datetime.fromisoformat(row["created_at"]) for row in rows]
    if len(rows)!=6000: errors.append(f"record_count:{len(rows)}")
    if counts!=Counter(COUNTS): errors.append(f"type_counts:{dict(counts)}")
    if (max(timestamps)-min(timestamps)).days<365: errors.append("coverage_under_12_months")
    if any(row.get("synthetic") is not True or row.get("data_class")!="DEMO_SYNTHETIC" for row in rows): errors.append("missing_synthetic_label")
    raw="\n".join(json.dumps(row,ensure_ascii=False) for row in rows)
    forbidden={"china_id":r"(?<!\d)\d{17}[\dXx](?!\d)","mobile":r"(?<!\d)1[3-9]\d{9}(?!\d)","exact_address":r"北京市[^\n]{0,30}(?:路|街|胡同)\d+号"}
    for name,pattern in forbidden.items():
        if re.search(pattern,raw): errors.append(f"forbidden_personal_pattern:{name}")
    return {"status":"PASS" if not errors else "FAIL","errors":errors,"record_count":len(rows),"type_counts":dict(counts),"coverage_start":iso(min(timestamps)),"coverage_end":iso(max(timestamps)),"coverage_days":(max(timestamps)-min(timestamps)).days}


def main():
    rng=random.Random(SEED);rows=[]
    for kind,count in COUNTS.items(): rows.extend(MAKERS[kind](rng,index) for index in range(1,count+1))
    rows.sort(key=lambda row:(row["created_at"],row["record_id"]));result=validate(rows)
    if result["status"]!="PASS": raise SystemExit(json.dumps(result,ensure_ascii=False))
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text("\n".join(json.dumps(row,ensure_ascii=False,separators=(",",":")) for row in rows)+"\n",encoding="utf-8")
    checksum=hashlib.sha256(OUT.read_bytes()).hexdigest();manifest={"dataset":"beijing_property_ops_6000","data_class":"DEMO_SYNTHETIC","synthetic":True,"seed":SEED,"generated_at":datetime.now(timezone.utc).isoformat(),"real_property_authorization":False,"contains_real_personal_data":False,"contains_real_company_facts":False,"allowed_use":["产品演示","回归测试","流程分析"],"prohibited_claims":["真实居民数据","真实账单","真实工单","真实物业公司经营事实"],"file":str(OUT.relative_to(ROOT)).replace("\\","/"),"sha256":checksum,"validation":result}
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    OPS_PUBLIC.parent.mkdir(parents=True,exist_ok=True);OPS_PUBLIC.write_text(json.dumps({"data_class":"OPS_PUBLIC","title":"北京市12345市民服务热线2022年度数据报告","source_url":"https://www.beijing.gov.cn/hudong/jpzt/2022ndsjbg/index.html","period":"2022","granularity":"公开年度聚合数据","allowed_use":"仅用于问题类别和趋势研究","prohibited_use":"不得推断任何居民、房屋、工单或投诉个案事实","contains_case_records":False},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False))


if __name__=="__main__": main()
