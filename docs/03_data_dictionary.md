# 03 数据字典（阶段 0）

> 本文是设计契约，不是迁移脚本；不创建数据库。示例值均为少量虚构值。隐私等级：P0 公开、P1 内部、P2 个人业务信息、P3 高敏感。除法定或合同要求外，建议到期后删除或匿名化。

## 通用约定

主键建议使用 UUID；时间使用 datetime（UTC 存储）；金额使用 decimal(12,2)；枚举由领域层统一维护；所有写表建议含 created_at、updated_at，并由 audit_logs 留痕。

| 表（中文名称） | 用途/主键 | 关键字段（类型；必填；示例） | 隐私/来源/保留建议 | 关系 |
|---|---|---|---|---|
| users（用户） | 身份与角色；user_id | role enum；是；居民，display_name varchar；是；李明，phone_masked varchar；否；138****0001，status enum；是；active | P2；用户授权/模拟；账号存续期+2年 | 1:N 绑定、工单、日志 |
| properties（房屋） | 小区房屋/公共区域；property_id | community_name varchar；是；示例家园，building_no varchar；否；3，unit_no varchar；否；2，room_no varchar；否；801，property_type enum；是；residential | P2；物业台账/模拟；房屋有效期+2年 | 1:N 绑定、工单、账单 |
| user_property_bindings（用户房屋绑定） | 用户与房屋归属；binding_id | user_id uuid；是，property_id uuid；是，binding_status enum；是；verified，verified_at datetime；否；2026-08-01T09:00:00Z | P2；授权/模拟；解绑+2年 | N:1 用户、房屋 |
| work_orders（工单） | 报修闭环主记录；work_order_id | work_order_no varchar；是；WO-DEMO-001，user_id/property_id uuid；是，raw_request text；是；公共照明不亮，standard_summary text；是，category/location/equipment/fault_description/impact_scope varchar；按规则必填，risk_level enum；是；low，priority enum；是；P2，status enum；是；待受理，assignee_id uuid；否，first_response_at/completed_at/closed_at datetime；否，resolution text；否，manual_escalation bool；是；false | P2；居民输入/模拟；关闭+3年 | N:1 用户、房屋；1:N 事件、评分 |
| work_order_events（工单事件） | 状态与处理时间线；event_id | work_order_id uuid；是，event_type enum；是；assigned，from_status/to_status enum；否，operator_id uuid；是，note text；否，occurred_at datetime；是 | P2；系统/人工；关闭+3年 | N:1 工单 |
| work_order_ratings（工单评价） | 居民服务评价；rating_id | work_order_id uuid；是且唯一，resident_id uuid；是，score smallint；是；5，comment text；否 | P2；居民输入；关闭+3年 | 1:1 工单 |
| announcements（公告） | 公告草稿、审核与发布记录；announcement_id | title/type/impact_scope/reason/precautions/contact/publisher_org varchar/text；是，starts_at/ends_at/published_at datetime；按状态必填，draft_content/short_content text；是，review_status enum；是；draft，reviewer_id uuid；否 | P1；物业输入/模拟；发布+3年 | N:1 审核人；仅人工发布 |
| bills（账单） | 只读费用账单；bill_id | property_id uuid；是，billing_period date；是；2026-07-01，fee_type enum；是；property_fee，amount_due decimal；是；120.00，due_date date；是，bill_status enum；是；unpaid | P2；模拟/未来系统只读接口；账期+5年 | N:1 房屋；1:N 缴费、核查 |
| payment_records（缴费记录） | 历史缴费凭据摘要；payment_id | bill_id uuid；是，paid_amount decimal；是；120.00，paid_at datetime；是，channel enum；是；mock，reference_no_masked varchar；否 | P2；模拟/未来支付只读接口；账期+5年 | N:1 账单 |
| bill_review_requests（费用核查申请） | 无法解释的费用争议；review_request_id | bill_id/user_id uuid；是，reason text；是，status enum；是；pending，handler_id uuid；否，result text；否 | P2；居民输入；结案+3年 | N:1 账单、用户 |
| inspection_tasks（巡检任务） | 巡检派发；inspection_task_id | area varchar；是；地下车库，task_type enum；是；fire_safety，assignee_id uuid；是，scheduled_at datetime；是，status enum；是；assigned | P1；物业计划/模拟；完成+2年 | 1:N 记录 |
| inspection_records（巡检记录） | 巡检文字/附件结果；inspection_record_id | task_id uuid；是，inspector_id uuid；是，description text；是， risk_level enum；是；medium，attachment_uri varchar；否，recorded_at datetime；是 | P1/P2附件；巡检输入；完成+3年 | N:1 任务；可触发整改 |
| rectification_orders（整改工单） | 巡检异常整改与复查；rectification_id | inspection_record_id uuid；是，work_order_id uuid；否，risk_level/status enum；是，assignee_id uuid；否，result text；否，rechecker_id uuid；否，closed_at datetime；否 | P1；系统/人工；关闭+3年 | N:1 巡检记录，可关联工单 |
| knowledge_documents（知识文档） | RAG 文档元数据；document_id | document_name/publisher/source_url/version varchar；是，effective_date/expiry_date date；是/否，applicable_community varchar；是，document_status enum；是；effective | P1；授权/公开资料；失效+3年 | 1:N 文本块 |
| knowledge_chunks（知识文本块） | 条款及向量索引元数据；chunk_id | document_id uuid；是，clause_title varchar；是，content text；是，chunk_index int；是，vector_ref varchar；否 | P1；文档切分；随文档 | N:1 文档 |
| audit_logs（审计日志） | 可追溯访问、工具与审批；audit_log_id | actor_id uuid；否，action/resource_type/resource_id varchar；是， result enum；是；denied，reason text；否，request_id varchar；是，occurred_at datetime；是 | P2；系统生成；至少3年 | 可关联所有业务实体 |

## 字段与关系补充

- 工单状态固定为：待补充信息、待受理、已受理、已派单、处理中、等待配件、待居民确认、已完成、已关闭、已取消；其变更仅通过 work_order_events 记录。
- 风险等级建议：low、medium、high、critical；high/critical 必填 manual_escalation=true 并写入审计。
- 知识回答引用 knowledge_documents 的文件名、版本、生效日期和 knowledge_chunks 的条款标题；失效文档不得作为确定性依据。
- 附件只保存受控存储引用与必要元数据，不将原图或任何敏感身份证明写入日志。

