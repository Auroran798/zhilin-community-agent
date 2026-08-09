# Stage 7 费用

账单和支付只读。bill_items 提供费用明细，BillingService.compare 仅比较同一房屋的两期账单并计算差异项。居民只能读取绑定房屋的账单、明细、支付历史和自身复核申请。

复核状态采用 submitted / under_review / resolved / rejected / cancelled 语义（兼容历史 pending/handled 数据）。系统没有 modify_bill、refund_payment、reduce_fee、delete_payment 或 mark_paid_manually 工具。
