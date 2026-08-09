# 阶段 2 API 契约

所有接口沿用 `{success,data,message,request_id}` 统一封装和 Bearer JWT。知识库接口包括：

- `POST /api/v1/knowledge/documents`：管理员上传，校验类型/大小/来源必填字段并哈希去重。
- `POST /api/v1/knowledge/documents/{id}/index`：创建可追踪索引任务并返回任务/解析结果。
- `POST /api/v1/knowledge/documents/{id}/versions`：管理员上传新版本，保留旧版本指纹并触发增量重索引。
- `POST /api/v1/knowledge/documents/{id}/submit-review`、`approve`、`activate`、`deactivate`：控制资料状态。
- `GET /api/v1/knowledge/documents`、`GET /api/v1/knowledge/ingestion-jobs`：管理员管理视图数据。
- `POST /api/v1/knowledge/query`：表单参数 `query`、`top_k`、可选 `document_type`、`include_history`；居民自动绑定本人小区。
- `POST /api/v1/knowledge/feedback`：参数 `query_log_id`、`rating`（1 或 -1）和可选评论；仅查询发起人可提交。

禁止普通用户上传、审核、看管理列表或读取历史资料。错误响应不泄漏内部路径、密钥或未授权文档内容。
