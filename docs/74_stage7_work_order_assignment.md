# Stage 7 报修与派单

maintenance_profiles 复用既有维修登录身份，maintenance_skills 和关联表表达技能。recommend_assignee 依次考虑维修类别需要的技能、服务楼栋、当前负载和可用状态；结果只是一条建议。

客服或经理必须通过 assign_work_order/API 明确确认，才会写入处理人、状态事件、审计和 WORK_ORDER_ASSIGNED 通知。既有旧 Demo 维修账号首次人工派单会创建保守的兼容 profile，避免破坏已授权任务队列。
