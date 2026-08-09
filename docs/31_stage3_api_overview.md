# 阶段 3 API

- `POST /api/v1/agent/sessions`：为当前认证用户创建会话。
- `POST /api/v1/agent/sessions/{id}/messages`：发送自然语言消息；可能返回 `awaiting_confirmation` 和预览。
- `POST /api/v1/agent/confirmations/{id}`：仅确认所有者可用 `confirm` 或 `cancel` 恢复中断；重复确认幂等。
- `GET /api/v1/agent/sessions/{id}`、`GET .../messages`：仅会话所有者可读。
- `GET|PUT|DELETE /api/v1/agent/memories`：用户自行查看、授权保存和删除长期记忆。

所有接口沿用 JWT 认证与统一错误响应。请求体中的用户、角色和房屋字段不被信任。
