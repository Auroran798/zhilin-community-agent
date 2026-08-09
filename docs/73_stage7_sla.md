# Stage 7 SLA

sla_policies 以类别和风险级别选择策略。当前 Demo 采用自然时间而非节假日服务日历；普通、优先、紧急和重大安全策略由演示种子数据提供。

- response_deadline：创建时间 + response_minutes
- processing_deadline：创建时间 + processing_minutes
- 剩余时间大于 20% 为 normal；不超过 20% 为 warning；截止后为 overdue；响应/完成后为 completed。

SLA 仅由 SLAService 计算。调度扫描生成幂等 SLA_WARNING / SLA_OVERDUE 站内通知。
