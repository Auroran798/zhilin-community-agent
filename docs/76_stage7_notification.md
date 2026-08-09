# Stage 7 通知中心

notifications 使用 notification_type:business_type:business_id:recipient 作为唯一幂等键。居民和员工均只能读取自己的通知并标记已读。

覆盖工单创建/派单/状态变化/完成、公告发布、费用复核结果、巡检任务、整改创建/到期/完成以及 SLA 预警/逾期。阶段 7 仅实现站内通知，不接入短信、微信或邮件。
