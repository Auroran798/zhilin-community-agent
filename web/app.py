import os
import json
import requests
import streamlit as st

st.set_page_config(page_title="智邻管家", layout="wide")
API = os.getenv("API_BASE_URL", "http://localhost:8000")

def call(method, path, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = "Bearer " + st.session_state.token
    response = requests.request(method, API + path, headers=headers, timeout=10, **kwargs)
    if not response.ok:
        try: st.error(response.json()["error"]["message"])
        except Exception: st.error("接口调用失败")
        return None
    payload = response.json()
    return payload.get("data", payload)

def show_table(path):
    data = call("GET", path)
    if data is not None: st.dataframe(data, width="stretch")

if "token" not in st.session_state:
    st.title("智邻管家｜物业基础业务系统")
    with st.form("login"):
        username = st.text_input("用户名", value="resident_demo")
        password = st.text_input("密码", type="password", value="DemoPass123!")
        if st.form_submit_button("登录"):
            response = requests.post(API + "/api/v1/auth/login", json={"username": username, "password": password}, timeout=10)
            if response.ok:
                st.session_state.token = response.json()["data"]["access_token"]
                st.session_state.user = response.json()["data"]["user"]
                st.rerun()
            st.error("登录失败" if not response.ok else "")
    st.caption("演示账号：resident_demo / service_demo / maintenance_demo / manager_demo")
else:
    user = st.session_state.user
    role = user["role"]
    st.sidebar.title("智邻管家")
    st.sidebar.caption(f"{user['display_name']}（{role}）")
    if st.sidebar.button("退出登录"):
        st.session_state.clear(); st.rerun()
    menu = {
        "resident": ["智能体对话", "我的房屋", "创建报修", "我的工单", "我的账单", "账单明细与复核", "公告", "通知中心", "智能问答"],
        "customer_service": ["智能体对话", "智能体人工处理", "工单管理", "公告草稿", "费用核查", "巡检整改", "设备台账", "通知中心", "真实公开案例"],
        "maintenance": ["智能体对话", "我的工单", "我的巡检任务", "我的整改任务", "设备台账", "通知中心"],
        "manager": ["智能体对话", "智能体人工处理", "管理看板", "真实公开案例", "调用链监控", "工单管理", "公告审核发布", "巡检整改", "设备台账", "通知中心", "审计日志", "知识库管理", "智能问答"]
    }[role]
    landing={"resident":"我的房屋","customer_service":"工单管理","maintenance":"我的工单","manager":"管理看板"}[role]
    page = st.sidebar.radio("功能菜单", menu, index=menu.index(landing))

    if page == "智能体对话":
        st.title("智邻管家智能体")
        st.caption("可协助报修、工单/账单查询、费用核查、制度问答和公告草稿。写入业务前会展示预览，须由您明确确认。安全事件会立即转人工。")
        if "agent_session" not in st.session_state:
            created=call("POST","/api/v1/agent/sessions")
            if created: st.session_state.agent_session=created["id"]
        if st.session_state.get("agent_session"):
            for message in call("GET",f"/api/v1/agent/sessions/{st.session_state.agent_session}/messages") or []:
                with st.chat_message("assistant" if message["role"]=="assistant" else "user"): st.write(message["content"])
            question=st.chat_input("例如：1号楼楼道灯不亮，请帮我报修")
            if question:
                result=call("POST",f"/api/v1/agent/sessions/{st.session_state.agent_session}/messages",json={"content":question})
                if result:
                    st.session_state.agent_pending=result if result.get("confirmation_id") else None
                    st.rerun()
            pending=st.session_state.get("agent_pending")
            if pending:
                st.subheader("待确认操作")
                st.json(pending["preview"])
                left,middle,right=st.columns(3)
                if left.button("确认执行",type="primary"):
                    call("POST",f"/api/v1/agent/confirmations/{pending['confirmation_id']}/confirm");st.session_state.agent_pending=None;st.rerun()
                with middle.popover("修改预览"):
                    changed=st.text_area("JSON 字段",value="{}",key="agent_preview_modify")
                    if st.button("提交修改"):
                        try:
                            revised=call("POST",f"/api/v1/agent/confirmations/{pending['confirmation_id']}/modify",json={"fields":json.loads(changed)})
                            if revised:st.session_state.agent_pending={**pending,**revised};st.rerun()
                        except json.JSONDecodeError:st.error("请输入合法 JSON")
                if right.button("取消操作"):
                    call("POST",f"/api/v1/agent/confirmations/{pending['confirmation_id']}/cancel");st.session_state.agent_pending=None;st.rerun()
    elif page == "智能问答":
        st.title("物业知识问答")
        st.caption("回答仅依据当前有效知识库，并展示来源；无法依据资料确认时会明确拒答。")
        with st.form("rag_query"):
            question=st.text_area("请输入物业问题", placeholder="例如：装修前需要办理哪些手续？")
            doc_type=st.text_input("资料类型筛选（可选）", placeholder="如 renovation_rule")
            submitted=st.form_submit_button("查询")
        if submitted and question.strip():
            payload={"query":question,"top_k":"5"}
            if doc_type.strip(): payload["document_type"]=doc_type.strip()
            answer=call("POST","/api/v1/knowledge/query",data=payload)
            if answer:
                if answer["answer_status"]=="answered": st.success(answer["answer"])
                else: st.warning(answer["answer"])
                if answer.get("scope_warning"): st.info(answer["scope_warning"])
                if answer.get("citations"):
                    st.subheader("引用来源")
                    st.dataframe(answer["citations"],width="stretch")
                st.session_state.last_rag_log=answer["query_log_id"]
        if st.session_state.get("last_rag_log"):
            c1,c2=st.columns(2)
            if c1.button("有帮助 👍"): call("POST","/api/v1/knowledge/feedback",data={"query_log_id":st.session_state.last_rag_log,"rating":"1"});st.success("已收到反馈")
            if c2.button("没有帮助 👎"): call("POST","/api/v1/knowledge/feedback",data={"query_log_id":st.session_state.last_rag_log,"rating":"-1"});st.info("已记录，将用于改进资料和检索")
    elif page == "智能体人工处理":
        st.title("智能体人工处理")
        reviews=call("GET","/api/v1/agent/human-reviews") or []
        st.dataframe(reviews,width="stretch")
        if reviews:
            review_id=st.selectbox("选择处理单",[x["id"] for x in reviews])
            result=st.text_area("处理结果",key="agent_review_result")
            if st.button("完成处理") and result.strip():
                if call("POST",f"/api/v1/agent/human-reviews/{review_id}/resolve",json={"result":result}):st.success("人工处理单已完成")
    elif page == "知识库管理":
        st.title("知识库管理")
        st.caption("正式文件应填写官方 URL、发布单位、版本、生效日期和效力状态；虚拟资料会按 synthetic 标识保存。")
        with st.expander("上传资料",expanded=False):
            with st.form("upload_knowledge"):
                file=st.file_uploader("文件",type=["pdf","docx","txt","md","html"])
                title=st.text_input("标题")
                source_type=st.selectbox("来源类型",["official_public_document","synthetic_community_document"])
                document_type=st.text_input("资料类型",value="community_rule")
                community=st.text_input("适用小区（虚拟资料填 Demo Garden）")
                source_url=st.text_input("官方来源 URL")
                publisher=st.text_input("发布单位")
                version=st.text_input("版本",value="1.0")
                if st.form_submit_button("上传") and file and title:
                    form={"title":title,"document_type":document_type,"source_type":source_type,"applicable_community":community,"source_url":source_url,"publisher":publisher,"version":version}
                    result=call("POST","/api/v1/knowledge/documents",data=form,files={"file":(file.name,file.getvalue(),file.type or "application/octet-stream")})
                    if result: st.success("已上传："+result["id"])
        documents=call("GET","/api/v1/knowledge/documents") or []
        st.dataframe(documents,width="stretch")
        if documents:
            selected=st.selectbox("选择资料",[x["id"] for x in documents])
            a,b,c,d=st.columns(4)
            if a.button("建立索引"): call("POST",f"/api/v1/knowledge/documents/{selected}/index")
            if b.button("提交审核"): call("POST",f"/api/v1/knowledge/documents/{selected}/submit-review")
            if c.button("审核并激活"): call("POST",f"/api/v1/knowledge/documents/{selected}/approve")
            if d.button("停用"): call("POST",f"/api/v1/knowledge/documents/{selected}/deactivate")
            with st.expander("上传新版本"):
                next_file=st.file_uploader("新版本文件",type=["pdf","docx","txt","md","html"],key="knowledge_version_file")
                next_version=st.text_input("新版本号",key="knowledge_version")
                summary=st.text_input("更新说明",key="knowledge_change")
                if st.button("保存并重建索引") and next_file and next_version:
                    data={"version":next_version,"change_summary":summary or "content update"}
                    result=call("POST",f"/api/v1/knowledge/documents/{selected}/versions",data=data,files={"file":(next_file.name,next_file.getvalue(),next_file.type or "application/octet-stream")})
                    if result: st.success("新版本已建立索引，待审核后生效")
        st.subheader("索引任务")
        st.dataframe(call("GET","/api/v1/knowledge/ingestion-jobs") or [],width="stretch")
    elif page == "我的房屋": show_table("/api/v1/properties/my")
    elif page == "我的工单":
        orders=call("GET","/api/v1/work-orders") or []
        st.dataframe(orders,width="stretch")
        if orders:
            selected=st.selectbox("选择工单",[x["id"] for x in orders],key="my_order_id")
            current=next(x for x in orders if x["id"]==selected)
            if role=="maintenance":
                if current["status"] in {"已派单","等待配件"} and st.button("开始处理"):
                    if call("POST",f"/api/v1/work-orders/{selected}/transition",json={"target_status":"处理中","note":"维修人员已开始处理"}):st.success("工单已进入处理中")
                if current["status"]=="处理中":
                    resolution=st.text_area("处理结果",key="work_order_resolution")
                    if st.button("提交居民确认") and resolution.strip():
                        if call("POST",f"/api/v1/work-orders/{selected}/transition",json={"target_status":"待居民确认","note":"维修处理完成","resolution":resolution}):st.success("已提交居民确认")
            elif role=="resident" and current["status"]=="待居民确认":
                if st.button("确认维修完成"):
                    if call("POST",f"/api/v1/work-orders/{selected}/transition",json={"target_status":"已完成","note":"居民确认完成"}):st.success("已确认完成")
            elif role=="resident" and current["status"]=="已完成":
                score=st.select_slider("服务评分",options=[1,2,3,4,5],value=5)
                comment=st.text_input("评价内容")
                if st.button("提交评价"):
                    if call("POST",f"/api/v1/work-orders/{selected}/rating",json={"score":score,"comment":comment}):st.success("评价已提交")
    elif page == "我的账单": show_table("/api/v1/bills")
    elif page == "账单明细与复核":
        items=call("GET","/api/v1/bills") or []; st.dataframe(items,width="stretch")
        if items:
            bill_id=st.selectbox("选择账单",[x["id"] for x in items])
            details=call("GET",f"/api/v1/bills/{bill_id}/details")
            if details: st.json(details)
            reason=st.text_area("复核原因")
            if st.button("提交费用复核") and reason.strip():
                if call("POST",f"/api/v1/bills/{bill_id}/review-requests",json={"reason":reason}):st.success("复核申请已提交")
    elif page == "公告": show_table("/api/v1/announcements")
    elif page == "通知中心":
        payload=call("GET","/api/v1/notifications") or {}; st.metric("未读通知",payload.get("unread_count",0)); items=payload.get("items",[]);st.dataframe(items,width="stretch")
        if items:
            notification_id=st.selectbox("选择通知",[x["id"] for x in items])
            if st.button("标记已读"):call("POST",f"/api/v1/notifications/{notification_id}/read");st.rerun()
    elif page == "管理看板":
        data = call("GET", "/api/v1/dashboard/summary")
        if data:
            cols = st.columns(4)
            for col, key, label in zip(cols, ["work_order_total","today_new","overdue","completion_rate"], ["工单总数","今日新增","超时","完成率"]):
                col.metric(label, data.get(key, 0))
            st.json(data)
            if st.button("执行到期调度（演示）"):
                result=call("POST","/api/v1/scheduler/run-due")
                if result:st.success("调度完成");st.json(result)
    elif page == "真实公开案例":
        st.title("真实公开历史案例")
        st.caption("仅展示已脱敏的纽约市 HPD 历史公共监管记录，不是中国物业数据，不代表任何地址的当前状态。")
        summary = call("GET", "/api/v1/public-real/summary")
        if summary:
            c1, c2 = st.columns(2)
            c1.metric("公开案例总数", summary.get("total", 0))
            c2.write("来源", summary.get("by_dataset", {}))
            st.write("物业类别分布", summary.get("by_category", {}))
        category = st.selectbox("物业类别（可选）", ["", "电梯", "给排水", "公共照明", "门禁", "消防设施", "停车", "装修扰民", "公共区域卫生", "配电设施", "道路和地面", "绿化", "其他"])
        query = st.text_input("已脱敏英文文本检索（可选）")
        params = []
        if category: params.append("category=" + category)
        if query.strip(): params.append("q=" + query.strip())
        suffix = ("?" + "&".join(params)) if params else ""
        result = call("GET", "/api/v1/public-real/cases" + suffix)
        if result:
            st.caption(result.get("notice", ""))
            st.dataframe(result.get("items", []), width="stretch")
    elif page == "调用链监控":
        st.title("调用链监控")
        st.caption("仅显示已脱敏的本地 Harness / MCP 调用记录。")
        metrics=call("GET","/api/v1/observability/metrics")
        if metrics: st.json(metrics)
        traces_payload=call("GET","/api/v1/observability/traces") or {}
        traces=traces_payload.get("items",[]) if isinstance(traces_payload,dict) else traces_payload
        st.dataframe(traces,width="stretch")
        if traces:
            trace_id=st.selectbox("查看调用链",[x["trace_id"] for x in traces])
            detail=call("GET",f"/api/v1/observability/traces/{trace_id}")
            if detail:
                st.subheader("Span");st.dataframe(detail["spans"],width="stretch")
                st.subheader("工具尝试");st.dataframe(detail["executions"],width="stretch")
    elif page == "审计日志": show_table("/api/v1/audit-logs")
    elif page == "创建报修":
        properties = call("GET", "/api/v1/properties/my") or []
        with st.form("create_order"):
            options = {f"{x['building_no']}号楼{x['unit_no']}单元{x['room_no']}":x["id"] for x in properties}
            p = st.selectbox("房屋", list(options)) if options else None
            category = st.selectbox("类别", ["电梯","给排水","公共照明","门禁","消防设施","停车","其他"])
            location = st.text_input("位置描述"); desc = st.text_area("故障描述")
            if st.form_submit_button("提交报修") and p:
                payload={"property_id":options[p],"original_description":desc,"summary":category+"报修","category":category,"location_description":location,"fault_description":desc}
                if call("POST","/api/v1/work-orders",json=payload,headers={"Idempotency-Key":str(__import__("uuid").uuid4())}): st.success("工单已创建")
    elif page == "工单管理":
        orders = call("GET","/api/v1/work-orders") or []; st.dataframe(orders,width="stretch")
        if orders:
            selected=st.selectbox("选择工单",[x["id"] for x in orders])
            if role=="customer_service" and st.button("受理选中工单"): call("POST",f"/api/v1/work-orders/{selected}/accept")
            if role in {"customer_service","manager"}:
                workers=call("GET","/api/v1/properties/my") or []
                st.caption("派单对象请使用维修人员 UUID（演示环境可从 API /docs 查询）。")
                worker_id=st.text_input("维修人员ID")
                if st.button("派单") and worker_id: call("POST",f"/api/v1/work-orders/{selected}/assign",json={"assignee_id":worker_id,"note":"页面派单"})
    elif page == "公告草稿":
        with st.form("announcement"):
            title=st.text_input("标题");content=st.text_area("内容");scope=st.text_input("影响范围")
            if st.form_submit_button("保存草稿"):
                if call("POST","/api/v1/announcements",json={"title":title,"announcement_type":"notice","content":content,"affected_scope":scope,"contact_information":"物业服务中心"}):st.success("草稿已保存")
        drafts=call("GET","/api/v1/announcements") or []
        st.dataframe(drafts,width="stretch")
        pending=[x for x in drafts if x["status"]=="draft"]
        if pending:
            draft_titles={x["id"]:x["title"] for x in pending}
            draft_id=st.selectbox("选择待提交草稿",list(draft_titles),format_func=lambda value:draft_titles[value])
            if st.button("提交人工审核"):
                if call("POST",f"/api/v1/announcements/{draft_id}/submit-review"):st.success("已提交经理审核")
    elif page == "公告审核发布":
        items=call("GET","/api/v1/announcements") or [];st.dataframe(items,width="stretch")
        if items:
            announcement_labels={x["id"]:f"{x['title']}（{x['status']}）" for x in items}
            aid=st.selectbox("公告",list(announcement_labels),format_func=lambda value:announcement_labels[value]);a=next(x for x in items if x["id"]==aid)
            if a["status"]=="pending_review" and st.button("审核通过"):call("POST",f"/api/v1/announcements/{aid}/approve")
            if a["status"]=="approved" and st.button("人工发布"):call("POST",f"/api/v1/announcements/{aid}/publish")
    elif page == "设备台账":
        st.title("设备台账")
        keyword=st.text_input("按名称、编码或位置搜索")
        suffix="?q="+keyword if keyword.strip() else ""
        items=call("GET","/api/v1/equipment"+suffix) or [];st.dataframe(items,width="stretch")
        if items:
            equipment_id=st.selectbox("查看设备历史",[x["id"] for x in items])
            if st.button("查看关联历史"):
                history=call("GET",f"/api/v1/equipment/{equipment_id}/history")
                if history:st.json(history)
    elif page == "我的巡检任务":
        tasks=call("GET","/api/v1/inspection-tasks") or [];st.dataframe(tasks,width="stretch")
        if tasks:
            task_id=st.selectbox("选择巡检任务",[x["id"] for x in tasks])
            with st.form("inspection_record"):
                description=st.text_area("巡检说明");abnormal=st.checkbox("发现异常");risk=st.selectbox("风险等级",["low","medium","high","critical"])
                if st.form_submit_button("提交巡检记录"):
                    if call("POST",f"/api/v1/inspection-tasks/{task_id}/records",json={"description":description,"abnormal":abnormal,"risk_level":risk},headers={"Idempotency-Key":str(__import__("uuid").uuid4())}):st.success("巡检记录已提交")
    elif page == "我的整改任务":
        items=call("GET","/api/v1/rectification-orders") or [];st.dataframe(items,width="stretch")
        if items:
            rid=st.selectbox("选择整改工单",[x["id"] for x in items])
            with st.form("rect_complete"):
                resolution=st.text_area("整改结果")
                if st.form_submit_button("提交整改结果"):
                    if call("POST",f"/api/v1/rectification-orders/{rid}/complete",json={"target_status":"待复查","resolution":resolution}):st.success("已提交复查")
    elif page == "费用核查":
        requests_data=call("GET","/api/v1/bill-review-requests") or [];st.dataframe(requests_data,width="stretch")
        if role=="customer_service" and requests_data:
            request_id=st.selectbox("选择核查申请",[x["id"] for x in requests_data])
            result=st.text_area("处理结果")
            if st.button("提交核查结果") and result: call("POST",f"/api/v1/bill-review-requests/{request_id}/handle",json={"result":result})
    elif page == "巡检整改":
        items=call("GET","/api/v1/rectification-orders") or [];st.dataframe(items,width="stretch")
        if role=="manager":
            st.subheader("创建巡检任务")
            with st.form("create_inspection_task"):
                area=st.selectbox("区域类型",["fire_safety","parking","electrical","public_area"]);location=st.text_input("位置描述");assignee=st.text_input("巡检人员ID")
                if st.form_submit_button("创建任务") and assignee:
                    import datetime
                    call("POST","/api/v1/inspection-tasks",json={"area_type":area,"location_description":location,"scheduled_at":datetime.datetime.now().isoformat(),"assignee_id":assignee})
        if role=="manager" and items:
            rid=st.selectbox("选择整改工单",[x["id"] for x in items])
            result=st.selectbox("复查结果",["已关闭","整改中"]);note=st.text_input("复查说明")
            if st.button("提交复查"):call("POST",f"/api/v1/rectification-orders/{rid}/review",json={"target_status":result,"note":note})
        st.caption("客服可通过 API 创建整改工单；管理人员可派发及复查。")
