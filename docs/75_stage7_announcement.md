# Stage 7 公告

Agent 只生成草稿。公告状态为 draft → pending_review → approved → published（可取消/过期）。提交审核会创建 announcement_approvals；经理人工审核记录申请人、审核人、意见和时间。

公告支持 all 与 building 定向范围。发布仅允许已人工审核的公告，随后生成去重站内通知并写审计。为保持 Stage 4 的 MCP 安全边界，发布接口由经理 API 工作流承担，不向 MCP/Agent 自动公开。
