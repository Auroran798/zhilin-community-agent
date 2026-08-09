# LangGraph 设计

节点顺序为 `normalize_input → detect_safety_risk → route_intent → select_skill → extract_fields → validate_fields`，随后按场景进入只读查询、操作预览或最终答复。写操作在 `request_user_confirmation` 调用 LangGraph `interrupt()`；`POST /agent/confirmations/{id}` 以同一会话 `thread_id` 及 `Command(resume=...)` 恢复，才会进入 `execute_business_tool`。

状态只保存标识、标准化输入、字段、风险、引用、预览和工具摘要；不保存密码、JWT、API Key 或 ORM 对象。checkpointer 为 `data/agent_checkpoints.sqlite`；业务会话、消息、确认与运行摘要同时持久化在主 SQLite，服务重启后可继续未过期的确认。
