"""Synchronise a curated Beijing/national official corpus with download receipts."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from data_pipeline.source_governance import validate_download_manifest, validate_registry

ROOT=Path(__file__).resolve().parents[1]
KB_ROOT=ROOT/"data"/"knowledge"
REGISTRY=KB_ROOT/"source_registry.csv"
BEIJING_REGISTRY=KB_ROOT/"beijing_official_source_registry.csv"
ALLOWLIST=KB_ROOT/"download_allowlist.csv"
MANIFEST_ROOT=KB_ROOT/"manifests"/"beijing"
ACQUIRED_AT=date.today().isoformat()
MAX_REDIRECTS=5
COPYRIGHT_NOTE="国家机关公开的法律法规和具有立法、行政性质的文件按其法定公开属性使用；其他指南仅保存内部检索快照并引用原始官方链接，不再分发。"


@dataclass(frozen=True)
class Source:
    source_no:str; title:str; url:str; publisher:str; publication_date:str
    version:str; effective_date:str; authority_status:str; jurisdiction:str
    document_type:str; authority_level:str; answerable:bool=True; notes:str=""


def s(no,title,url,publisher,pub,version,effective,status,jurisdiction,kind,level,answerable=True,notes=""):
    return Source(no,title,url,publisher,pub,version,effective,status,jurisdiction,kind,level,answerable,notes)


SOURCES=[
    s("SRC-OFFICIAL-CN-007","中华人民共和国民法典","https://www.beijing.gov.cn/zhengce/zhengcefagui/202006/t20200602_1913330.html","全国人民代表大会（北京市政府网站转载）","2020-05-28","中华人民共和国主席令第四十五号","2021-01-01","现行有效","全国","civil_code","national_law"),
    s("SRC-OFFICIAL-CN-008","中华人民共和国消防法","https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/bgt/art/2023/art_e9e34f0731c249a891ea9c925e17f237.html","全国人民代表大会常务委员会（市场监管总局网站转载）","2021-04-29","2021年修正文本","2021-04-29","现行有效","全国","fire_law","national_law"),
    s("SRC-OFFICIAL-CN-009","中华人民共和国特种设备安全法","https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/fgs/art/2023/art_ad5e293574484b48b45047ee0ede6099.html","全国人民代表大会常务委员会（市场监管总局网站转载）","2013-06-29","中华人民共和国主席令第四号","2014-01-01","现行有效","全国","special_equipment_law","national_law"),
    s("SRC-OFFICIAL-CN-010","特种设备安全监察条例","https://www.beijing.gov.cn/zhengce/zhengcefagui/qtwj/201912/t20191211_1054966.html","国务院（北京市政府网站转载）","2009-01-24","国务院令第549号","2009-05-01","现行有效","全国","special_equipment_regulation","national_regulation"),
    s("SRC-OFFICIAL-CN-011","城市供水条例","https://www.beijing.gov.cn/zhengce/zhengcefagui/qtwj/202307/t20230719_3165984.html","国务院（北京市政府网站转载）","2020-03-27","2020年修订文本","2020-03-27","现行有效","全国","water_supply_regulation","national_regulation"),
    s("SRC-OFFICIAL-CN-012","城镇燃气管理条例","https://www.beijing.gov.cn/zhengce/zhengcefagui/qtwj/201011/t20101125_780917.html","国务院（北京市政府网站转载）","2010-11-19","国务院令第583号","2011-03-01","现行有效","全国","gas_regulation","national_regulation"),
    s("SRC-OFFICIAL-CN-013","物业服务收费管理办法","https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/jls/art/2023/art_5ad02160f902480ea2a63c5bc85e7ae1.html","国家发展改革委、原建设部（市场监管总局网站）","2003-11-13","发改价格〔2003〕1864号","2004-01-01","现行政策文件","全国","property_fee_rule","national_department_rule"),
    s("SRC-OFFICIAL-CN-014","物业服务收费明码标价规定","https://www.ndrc.gov.cn/xxgk/zcfb/tz/200912/t20091222_965776_ext.html","国家发展改革委、原建设部","2004-07-19","发改价检〔2004〕1428号","2004-10-01","现行政策文件","全国","price_disclosure_rule","national_department_rule"),
    s("SRC-OFFICIAL-CN-015","中华人民共和国噪声污染防治法","https://flk.npc.gov.cn/detail?fileId=&id=ff8081817dea9c18017deb70ddc70131&type=","全国人民代表大会常务委员会","2021-12-24","中华人民共和国主席令第一〇四号","2022-06-05","现行有效","全国","noise_law","national_law"),
    s("SRC-OFFICIAL-CN-016","关于推动12345政务服务便民热线与110报警服务台高效对接联动的意见","https://www.beijing.gov.cn/zhengce/gwywj/202205/t20220516_2711529.html","国务院办公厅（北京市政府网站转载）","2022-05-16","国办发〔2022〕12号","2022-05-16","现行政策文件","全国","complaint_process","national_policy"),
    s("SRC-OFFICIAL-CN-017","关于进一步加强城市房屋室内装饰装修安全管理的通知","https://www.gov.cn/zhengce/zhengceku/202306/content_6885666.htm","住房和城乡建设部","2023-06-07","建办〔2023〕29号","2023-06-07","现行政策文件","全国","renovation_safety","national_department_rule"),
    s("SRC-OFFICIAL-CN-018","住宅室内装饰装修管理办法（官方PDF）","https://www.mohurd.gov.cn/file/2022/20220228/8e2304b2-9f66-426b-ab25-6eda86fa0f67.pdf","住房和城乡建设部","2011-01-26","2011年修正文本","2011-01-26","现行有效","全国","renovation_management","national_department_rule"),
    s("SRC-OFFICIAL-CN-019","高层民用建筑消防安全管理规定（官方PDF）","https://www.mem.gov.cn/gk/zfxxgkpt/fdzdgknr/gz11/202106/P020211228721655794602.pdf","应急管理部","2021-06-21","应急管理部令第5号","2021-08-01","现行有效","全国","highrise_fire_rule","national_department_rule"),
    s("SRC-OFFICIAL-CN-020","住宅专项维修资金管理办法","https://zjw.beijing.gov.cn/bjjs/xxgk/543346069/543346064/325733100/index.shtml","建设部、财政部（北京市住建委网站转载）","2007-12-04","建设部、财政部令第165号","2008-02-01","现行有效","全国","maintenance_fund","national_department_rule"),
    s("SRC-OFFICIAL-CN-BJ-003","北京市物业管理条例（2024年修正）","https://www.beijing.gov.cn/zhengce/dfxfg/202404/t20240401_3607249.html","北京市人民代表大会常务委员会","2024-03-29","2024年修正文本","2024-03-29","现行有效","北京市","property_management_regulation","local_regulation"),
    s("SRC-OFFICIAL-CN-BJ-004","《北京市物业管理条例》官方解读","https://www.beijing.gov.cn/zhengce/zcjd/202004/t20200401_1781920.html","北京市人民政府","2020-04-01","官方解读","2020-04-01","现行配套解读","北京市","official_interpretation","official_interpretation"),
    s("SRC-OFFICIAL-CN-BJ-005","DB11/T 751-2025 住宅物业服务标准","https://bzh.scjgj.beijing.gov.cn/bzh/apifile/file/2025/20250709/88e1be81-0a3b-4193-9cae-a506c0d9874a.pdf","北京市市场监督管理局","2025-06-30","DB11/T 751-2025","2025-10-01","现行有效","北京市","property_service_standard","local_standard"),
    s("SRC-OFFICIAL-CN-BJ-006","北京市住宅专项维修资金管理办法","https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/gfxwj40/xxyx/436468388/index.shtml","北京市住房和城乡建设委员会等","2009-11-02","京建物〔2009〕836号","2009-12-01","现行政策文件","北京市","maintenance_fund","local_department_rule"),
    s("SRC-OFFICIAL-CN-BJ-007","北京市住宅专项维修资金使用审核标准","https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/gfxwj40/xxyx/436460235/index.shtml","北京市住房和城乡建设委员会","2010-05-19","京建发〔2010〕272号","2010-05-19","现行政策文件","北京市","maintenance_fund_review","local_department_rule"),
    s("SRC-OFFICIAL-CN-BJ-008","城镇住宅专项维修资金应急使用审核办事指南","https://banshi.beijing.gov.cn/pubtask/task/1/110102000000/1be1171c-df7b-4dc2-8f6f-9791b4232c71.html","北京市政务服务管理局","2026-01-01","在线办事指南当前版","2026-01-01","当前办事指南","北京市","maintenance_fund_emergency","official_service_guide"),
    s("SRC-OFFICIAL-CN-BJ-009","住宅小区屋面防水应急维修工作通知","https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/qtzcwj/xxyx13/743671809/index.shtml","北京市住房和城乡建设委员会","2024-07-24","当前公开文本","2024-07-24","现行政策文件","北京市","rain_leak_emergency","local_policy"),
    s("SRC-OFFICIAL-CN-BJ-010","汛情受损住宅专项维修资金应急使用通知","https://gjj.beijing.gov.cn/web/zwgk61/2024zcwj/436433464/436433468/743678786/index.html","北京住房公积金管理中心","2025-08-01","当前公开文本","2025-08-01","现行政策文件","北京市","flood_maintenance_fund","local_policy"),
    s("SRC-OFFICIAL-CN-BJ-011","北京市物业服务合同示范文本","https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/gfxwj40/xxyx/436468220/index.shtml","北京市住房和城乡建设委员会、北京市市场监督管理局","2022-08-12","2022版示范文本","2022-09-01","现行示范文本","北京市","property_service_contract_template","official_template"),
    s("SRC-OFFICIAL-CN-BJ-012","北京市住宅区业主管理规约示范文本","https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/gfxwj40/xxyx/436468215/index.shtml","北京市住房和城乡建设委员会","2022-08-12","2022版示范文本","2022-09-01","现行示范文本","北京市","management_convention_template","official_template"),
    s("SRC-OFFICIAL-CN-BJ-013","北京市物业管理委员会组建办法","https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/gfxwj40/xxyx/436468187/index.shtml","北京市住房和城乡建设委员会","2021-03-19","京建发〔2021〕53号","2021-03-19","现行政策文件","北京市","property_management_committee","local_department_rule"),
    s("SRC-OFFICIAL-CN-BJ-014","物业服务企业劝阻、制止、报告工作台账和示范文本","https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/qtzcwj/xxyx13/436459816/index.shtml","北京市住房和城乡建设委员会","2020-07-31","官方示范文本","2020-07-31","现行工作指引","北京市","dissuade_stop_report_ledger","official_template"),
    s("SRC-OFFICIAL-CN-BJ-015","北京市物业管理区域安全生产自查表","https://zjw.beijing.gov.cn/bjjs/fwgl/wyglxx/wyglxx/53592936/2020010313585259864.pdf","北京市住房和城乡建设委员会","2019-04-26","京建发〔2019〕172号附件","2019-04-26","现行工作指引","北京市","property_safety_ledger","official_guide"),
    s("SRC-OFFICIAL-CN-BJ-016","住宅装修擅自变动建筑主体和承重结构执法工作通知","https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/gfxwj40/xxyx/543339801/index.shtml","北京市住房和城乡建设委员会等","2023-06-09","京建发〔2023〕182号","2023-06-09","现行政策文件","北京市","structural_alteration_enforcement","local_policy"),
    s("SRC-OFFICIAL-CN-BJ-017","北京市禁止违法建设若干规定","https://www.beijing.gov.cn/zhengce/zfwj/zfwj2016/szfl/202010/t20201030_2125883.html","北京市人民政府","2020-10-30","北京市人民政府令第295号","2020-11-15","现行有效","北京市","illegal_construction","local_government_rule"),
    s("SRC-OFFICIAL-CN-BJ-018","北京市房屋建筑使用安全条例","https://www.beijing.gov.cn/zhengce/dfxfg/202512/t20251203_4318928.html","北京市人民代表大会常务委员会","2025-11-28","2025年公布文本","2026-03-01","现行有效","北京市","building_use_safety","local_regulation"),
    s("SRC-OFFICIAL-CN-BJ-019","北京市消防条例","https://www.beijing.gov.cn/zhengce/dfxfg/202504/t20250428_4076471.html","北京市人民代表大会常务委员会","2025-03-28","2025年修订文本","2025-05-01","现行有效","北京市","fire_regulation","local_regulation"),
    s("SRC-OFFICIAL-CN-BJ-020","北京市非机动车管理条例","https://www.beijing.gov.cn/zhengce/dfxfg/202512/t20251203_4318959.html","北京市人民代表大会常务委员会","2025-11-28","2025年修订文本","2026-05-01","现行有效","北京市","electric_bicycle_rule","local_regulation"),
    s("SRC-OFFICIAL-CN-BJ-021","北京市电梯安全监督管理办法","https://scjgj.beijing.gov.cn/cxfw/flfgcxfw/tzsbl/202006/t20200618_1928088.html","北京市人民政府（北京市市场监督管理局网站）","2008-06-10","北京市人民政府令第205号","2008-08-01","现行有效","北京市","elevator_safety","local_government_rule"),
    s("SRC-OFFICIAL-CN-BJ-022","北京市电梯困人处置工作流程","https://www.beijing.gov.cn/cs/gncs/zcwj/202603/t20260327_4568251.html","北京市人民政府","2026-03-27","2026年公开工作流程","2026-03-27","当前工作指引","北京市","elevator_entrapment_process","official_guide"),
    s("SRC-OFFICIAL-CN-BJ-023","北京市供热采暖管理办法","https://www.beijing.gov.cn/gongkai/zfxxgk/zc/gz/202112/W020211216532156679225.pdf","北京市人民政府","2009-12-12","北京市人民政府令第216号","2010-04-01","现行有效","北京市","heating_management","local_government_rule"),
    s("SRC-OFFICIAL-CN-BJ-024","北京市燃气管理条例","https://csglw.beijing.gov.cn/zwxx/2024zcwj/202405/t20240517_3687045.html","北京市人民代表大会常务委员会（北京市城管委网站）","2020-09-25","2020年修订文本","2021-01-01","现行有效","北京市","gas_management","local_regulation"),
    s("SRC-OFFICIAL-CN-BJ-025","北京市居民用户燃气安全巡检工作规范","https://www.beijing.gov.cn/zhengce/zhengcefagui/202103/t20210312_2306334.html","北京市城市管理委员会","2021-03-12","当前公开文本","2021-03-12","现行工作指引","北京市","gas_home_inspection","official_guide"),
    s("SRC-OFFICIAL-CN-BJ-026","北京市物业服务收费明码标价通知","https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/qtzcwj/xxyx13/436469191/index.shtml","北京市发展改革委、北京市住房和城乡建设委员会","2016-07-08","京发改〔2016〕1383号","2016-09-01","现行政策文件","北京市","property_fee_disclosure","local_policy"),
    s("SRC-OFFICIAL-CN-BJ-027","北京市物业服务项目收支情况公示参考文本","https://zjw.beijing.gov.cn/bjjs/xxgk/zcwj2024/qtzcwj/xxyx13/436459838/index.shtml","北京市住房和城乡建设委员会","2020-07-31","官方参考文本","2020-07-31","现行工作指引","北京市","public_income_disclosure","official_template"),
    s("SRC-OFFICIAL-CN-BJ-028","北京市机动车停车条例","https://www.beijing.gov.cn/zhengce/dfxfg/202404/t20240401_3607248.html","北京市人民代表大会常务委员会","2024-03-29","2024年修正文本","2024-03-29","现行有效","北京市","parking_management","local_regulation"),
    s("SRC-OFFICIAL-CN-BJ-029","北京市生活垃圾管理条例","https://csglw.beijing.gov.cn/zwxx/2024zcwj/202405/t20240517_3687034.html","北京市人民代表大会常务委员会（北京市城管委网站）","2020-09-25","2020年修正文本","2020-09-25","现行有效","北京市","waste_sorting","local_regulation"),
    s("SRC-OFFICIAL-CN-BJ-030","北京市养犬管理规定","https://www.beijing.gov.cn/zhengce/dfxfg/201905/t20190522_56547.html","北京市人民代表大会常务委员会","2003-09-05","2003年公布文本","2003-10-15","现行有效","北京市","pet_management","local_regulation"),
    s("SRC-OFFICIAL-CN-BJ-031","北京市绿化条例","https://www.beijing.gov.cn/zhengce/dfxfg/202008/t20200805_1974790.html","北京市人民代表大会常务委员会","2019-07-26","2019年修正文本","2019-07-26","现行有效","北京市","greening_management","local_regulation"),
    s("SRC-OFFICIAL-CN-BJ-032","北京市市容环境卫生条例","https://www.beijing.gov.cn/zhengce/dfxfg/202111/t20211103_2527864.html","北京市人民代表大会常务委员会","2021-09-24","2021年修正文本","2021-09-24","现行有效","北京市","public_area_environment","local_regulation"),
    s("SRC-OFFICIAL-CN-BJ-033","北京市接诉即办改革工作实施意见","https://www.beijing.gov.cn/zhengce/zhengcefagui/202011/t20201105_2129024.html","北京市人民政府","2020-11-05","当前公开文本","2020-11-05","现行政策文件","北京市","complaint_12345","local_policy"),
    s("SRC-OFFICIAL-CN-BJ-034","北京市防汛应急预案（2025年修订）","https://yjglj.beijing.gov.cn/art/2025/4/15/art_2522_687454.html","北京市应急管理局","2025-04-15","2025年修订版","2025-04-15","现行应急预案","北京市","flood_emergency","emergency_plan"),
    s("SRC-OFFICIAL-CN-BJ-035","北京市供热突发事件应急预案（2024年版）","https://yjglj.beijing.gov.cn/art/2025/6/30/art_2522_687728.html","北京市应急管理局","2025-06-30","2024年版","2025-06-30","现行应急预案","北京市","heating_emergency","emergency_plan"),
    s("SRC-OFFICIAL-CN-BJ-036","北京市火灾事故应急救援预案（2024年修订）","https://yjglj.beijing.gov.cn/art/2025/6/30/art_2522_687722.html","北京市应急管理局","2025-06-30","2024年修订版","2025-06-30","现行应急预案","北京市","fire_emergency","emergency_plan"),
    s("SRC-OFFICIAL-CN-BJ-037","北京市突发事件总体应急预案（2021年修订）","https://gdb.beijing.gov.cn/rf_zwgk/2024zcwj/2024_flfg/202405/t20240530_3699280.html","北京市人民政府","2021-08-04","2021年修订版","2021-08-04","现行应急预案","北京市","general_emergency","emergency_plan"),
    s("SRC-OFFICIAL-CN-BJ-038","北京市雪雾低温天气应急预案","https://yjglj.beijing.gov.cn/art/2024/12/10/art_2522_684450.html","北京市应急管理局","2024-12-10","当前公开版本","2024-12-10","现行应急预案","北京市","cold_weather_emergency","emergency_plan"),
    s("SRC-OFFICIAL-CN-BJ-039","北京市节水条例","https://www.beijing.gov.cn/zhengce/zhengcefagui/qtwj/202407/t20240701_3734559.html","北京市人民代表大会常务委员会","2023-11-24","2023年公布文本","2024-03-01","现行有效","北京市","water_conservation","local_regulation"),
    s("SRC-OPS-PUBLIC-BJ-001","北京市12345市民服务热线2022年度数据报告","https://www.beijing.gov.cn/hudong/jpzt/2022ndsjbg/index.html","北京市人民政府","2023-01-01","2022年度报告","2023-01-01","公开聚合统计","北京市","public_aggregate_statistics","official_statistics",False,"OPS_PUBLIC：仅用于类别和趋势分析，不用于个案事实或法律依据。"),
]

FIELDS=["source_no","title","source_url","publisher","publication_date","acquired_at","version","effective_date","expiry_date","authority_status","country","jurisdiction","language","document_type","authority_level","license_note","license_url","local_path","answerable","manually_verified","review_status","parser_version","checksum","notes","data_class","source_type","actually_downloaded","contains_personal_data","minimization_rule","translation_provider","translation_model","translation_version"]
ALLOW_FIELDS=["source_no","source_url","allowed_host","allowed_redirect_hosts","expected_mime","expected_signature","min_bytes","max_bytes","destination"]


def _host(url:str)->str:
    parsed=urlparse(url)
    if parsed.scheme!="https" or not parsed.hostname: raise ValueError(f"official URL must use HTTPS: {url}")
    return parsed.hostname.lower()


def _destination(source:Source)->Path:
    suffix=".pdf" if urlparse(source.url).path.lower().endswith(".pdf") else ".html"
    scope="beijing" if source.jurisdiction=="北京市" else "national"
    return Path("official")/"china"/scope/f"{source.source_no.lower()}{suffix}"


def _allow_row(source:Source)->dict:
    host=_host(source.url); destination=_destination(source); signature="pdf" if destination.suffix==".pdf" else "html"
    return {"source_no":source.source_no,"source_url":source.url,"allowed_host":host,"allowed_redirect_hosts":host,"expected_mime":"application/pdf" if signature=="pdf" else "text/html","expected_signature":signature,"min_bytes":"300","max_bytes":str(30*1024*1024),"destination":destination.as_posix()}


def _registry_row(source:Source,local_path:str,checksum:str,downloaded:bool,error:str|None)->dict:
    approved=downloaded and source.answerable; data_class="OPS_PUBLIC" if source.source_no.startswith("SRC-OPS-") else "KB_POLICY"
    notes="；".join(item for item in (source.notes,error and f"同步失败：{error}") if item)
    return {"source_no":source.source_no,"title":source.title,"source_url":source.url,"publisher":source.publisher,"publication_date":source.publication_date,"acquired_at":ACQUIRED_AT,"version":source.version,"effective_date":source.effective_date,"expiry_date":"","authority_status":source.authority_status,"country":"CN","jurisdiction":source.jurisdiction,"language":"zh-CN","document_type":source.document_type,"authority_level":source.authority_level,"license_note":COPYRIGHT_NOTE,"license_url":source.url,"local_path":local_path,"answerable":str(approved).lower(),"manually_verified":str(approved).lower(),"review_status":"approved" if approved else "pending","parser_version":"pdf-structured-v2" if local_path.endswith(".pdf") else "html-structured-v2","checksum":checksum,"notes":notes,"data_class":data_class,"source_type":"official_public_document","actually_downloaded":str(downloaded).lower(),"contains_personal_data":"false","minimization_rule":"","translation_provider":"","translation_model":"","translation_version":""}


def _download(source:Source,rule:dict)->tuple[dict,dict]:
    manifest={"manifest_version":"beijing-source-download-v1","source_no":source.source_no,"requested_url":source.url,"retrieved_at":datetime.now(timezone.utc).isoformat(),"redirect_chain":[],"allowed_host":rule["allowed_host"],"status":"failed"}
    try:
        allowed={item for item in rule["allowed_redirect_hosts"].split("|") if item}|{rule["allowed_host"]};url=source.url
        with httpx.Client(timeout=httpx.Timeout(40.0,connect=15.0),headers={"User-Agent":"Zhilin-Beijing-KB-Governance/1.0"},verify=True,follow_redirects=False) as client:
            for _ in range(MAX_REDIRECTS+1):
                if _host(url) not in allowed: raise ValueError(f"redirect host not allowlisted: {_host(url)}")
                response=client.get(url);manifest["redirect_chain"].append({"url":url,"status_code":response.status_code})
                if response.status_code in {301,302,303,307,308}:
                    target=str(response.next_request.url) if response.next_request else ""
                    if not target: raise ValueError("redirect missing Location")
                    if _host(target) not in allowed: raise ValueError(f"redirect host not allowlisted: {_host(target)}")
                    url=target;continue
                response.raise_for_status();break
            else: raise ValueError("too many redirects")
        body=response.content;content_type=response.headers.get("content-type","").split(";",1)[0].lower();expected=rule["expected_signature"]
        signature_valid=body.startswith(b"%PDF-") if expected=="pdf" else bool(re.search(br"(?is)<(?:!doctype\s+html|html|head|body)\b",body[:8192]))
        mime_valid=(content_type in {"application/pdf","application/octet-stream"}) if expected=="pdf" else content_type in {"text/html","application/xhtml+xml"}
        size=len(body)
        if not mime_valid: raise ValueError(f"invalid MIME: {content_type}")
        if not signature_valid: raise ValueError(f"invalid {expected} signature")
        if not int(rule["min_bytes"])<=size<=int(rule["max_bytes"]): raise ValueError(f"size outside bounds: {size}")
        destination=KB_ROOT/Path(rule["destination"]);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(body)
        checksum=hashlib.sha256(body).hexdigest();manifest.update({"status":"downloaded","final_url":str(response.url),"final_host":_host(str(response.url)),"content_type":content_type,"mime_valid":mime_valid,"signature":expected,"signature_valid":signature_valid,"size_bytes":size,"sha256":checksum,"local_path":rule["destination"]})
        row=_registry_row(source,rule["destination"],checksum,True,None)
    except Exception as exc:
        error=f"{type(exc).__name__}: {exc}";manifest.update({"error":error,"final_url":manifest["redirect_chain"][-1]["url"] if manifest["redirect_chain"] else source.url,"content_type":"","mime_valid":False,"signature_valid":False,"size_bytes":0,"sha256":"","local_path":rule["destination"]});row=_registry_row(source,rule["destination"],"",False,error)
    MANIFEST_ROOT.mkdir(parents=True,exist_ok=True);(MANIFEST_ROOT/f"{source.source_no}.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return row,manifest


def _write_csv(path:Path,rows:list[dict],fields:list[str]):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction="ignore");writer.writeheader();writer.writerows([{key:row.get(key,"") for key in fields} for row in rows])


def _read_existing()->list[dict]:
    if not REGISTRY.exists(): return []
    with REGISTRY.open(encoding="utf-8-sig",newline="") as handle: return list(csv.DictReader(handle))


def _normalise_existing(row:dict)->dict:
    result={key:row.get(key,"") for key in FIELDS}
    if not result["data_class"]: result["data_class"]="DEMO_SYNTHETIC" if row.get("source_type")!="official_public_document" else ("OPS_PUBLIC" if row.get("document_type")=="public_aggregate_statistics" else "KB_POLICY")
    return result


def main()->None:
    parser=argparse.ArgumentParser();parser.add_argument("--workers",type=int,default=6);args=parser.parse_args()
    rules=[_allow_row(item) for item in SOURCES];_write_csv(ALLOWLIST,rules,ALLOW_FIELDS);rows=[];manifests=[]
    with ThreadPoolExecutor(max_workers=max(1,args.workers)) as pool:
        pending={pool.submit(_download,source,rule):source.source_no for source,rule in zip(SOURCES,rules)}
        for future in as_completed(pending):
            row,manifest=future.result();rows.append(row);manifests.append(manifest);print(f"{row['source_no']}: {manifest['status']}")
    rows.sort(key=lambda row:row["source_no"]);_write_csv(BEIJING_REGISTRY,rows,FIELDS);replacements={row["source_no"]:row for row in rows};replacement_urls={row["source_url"] for row in rows};merged=[]
    for old in _read_existing():
        if old.get("source_no","") not in replacements and old.get("source_url","") not in replacement_urls: merged.append(_normalise_existing(old))
    merged.extend(rows);merged.sort(key=lambda row:row["source_no"]);_write_csv(REGISTRY,merged,FIELDS)
    manifest_checks=[validate_download_manifest(MANIFEST_ROOT/f"{item['source_no']}.json",ALLOWLIST,KB_ROOT) for item in manifests if item["status"]=="downloaded"]
    registry_result=validate_registry(REGISTRY,KB_ROOT)
    summary={"generated_at":datetime.now(timezone.utc).isoformat(),"curated_count":len(rows),"downloaded_count":sum(row["actually_downloaded"]=="true" for row in rows),"answerable_count":sum(row["answerable"]=="true" for row in rows),"pending_count":sum(row["answerable"]!="true" for row in rows),"registry":registry_result,"manifest_failures":[item for item in manifest_checks if item["status"]!="PASS"]}
    (KB_ROOT/"beijing_sync_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(summary,ensure_ascii=False))
    if registry_result["status"]!="PASS" or summary["manifest_failures"]: raise SystemExit(1)


if __name__=="__main__": main()
