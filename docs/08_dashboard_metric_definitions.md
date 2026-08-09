# 08 看板指标定义

| 指标 | 定义/公式 | 数据来源 | 时间范围/空值 | 取消/未关闭 |
|---|---|---|---|---|
| 工单总数 | work_orders 行数 | work_orders | 全量；空为0 | 含取消、含未关闭 |
| 今日新增 | created_at 为今日 | work_orders | UTC 当日；空为0 | 含取消 |
| 各状态数量 | 按 status 聚合 | work_orders | 全量；空为0 | 分状态 |
| 超时 | 当前时间超过优先级 SLA 且未关闭/取消 | work_orders | 当前实时；空为0 | 不含取消、含未关闭 |
| 完成率 | 已关闭/总数×100 | work_orders | 全量；总数0为0 | 分子不含取消 |
| 平均满意度 | score 平均值 | work_order_ratings | 全量；空为null | 仅已评价 |

