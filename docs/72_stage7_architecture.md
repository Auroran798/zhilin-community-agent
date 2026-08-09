# Stage 7 架构

Stage 7 在既有 FastAPI + SQLAlchemy + LangGraph + MCP/Harness 架构上增加 api/stage7.py 确定性领域服务。Agent/Skill 只将自然语言转换为受限工具输入；SLA、账单、审批、通知收件人、计划频率、状态机和权限均由服务端执行。

    Agent/Streamlit → API/RBAC → Stage7 Service → ORM/Audit/Notification
                             ↘ Harness/MCP（受控工具）

Public Real 表没有外键指向居民、房屋、账单或员工表，保持只读数据边界。
