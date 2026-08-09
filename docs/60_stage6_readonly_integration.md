# 阶段 6：只读物业系统适配器

本阶段实现的是“受控合成上游 + 只读接口”的接入准备，不是对真实物业生产系统的对接。默认配置 `STAGE6_READONLY_INTEGRATION_ENABLED=false`；在获得合作方、数据授权、脱敏方案、人工兜底人与退出机制的书面确认前，必须保持关闭。

## 已实现的边界

- `PropertySystemAdapter` 只有健康检查、工单列表和工单详情三个读取能力，不定义创建、修改、派单、支付或公告发布方法。
- 所有上游工单被映射为统一的 `ExternalWorkOrder`：外部标识、来源系统、脱敏房屋引用、状态、分类、优先级、摘要、位置、风险和时间戳。
- 当前 `demo` 适配器仅读取 `data/external_reference/demo_property_work_orders.json` 中的合成样本，不含居民姓名、电话、精确地址、支付或附件。
- 路由仅管理员可访问，读取操作写入审计日志；上游不可用时返回 503，明确不推断或伪造工单数据。
- `POST /api/v1/integrations/property-systems/work-orders` 不存在；适配器接口本身也没有写入方法。
- 智能体可识别“外部工单 / 上游工单 / 试点工单 / 物业系统工单”查询，并通过 Harness 走同一适配器与审计链；非管理员请求被拒绝。

## 受控演示启用方式

仅用于本地验证时，在 `.env` 设置：

```dotenv
STAGE6_READONLY_INTEGRATION_ENABLED=true
PROPERTY_SYSTEM_ADAPTER=demo
```

然后以管理员身份调用：

- `GET /api/v1/integrations/property-systems/status`
- `GET /api/v1/integrations/property-systems/work-orders?limit=20&offset=0`
- `GET /api/v1/integrations/property-systems/work-orders/{external_id}`

## 对接真实供应商前的准入清单

1. 合作物业、试点负责人、可读取的数据范围和停用/退出机制均已明确。
2. 历史工单和制度文件均已合法授权、脱敏，且真实数据目录与 Demo 数据隔离。
3. 完成供应商字段映射、缺失/冲突处理、超时/重试、权限和审计设计；字段未知时记录问题，不能猜测。
4. 以新的供应商适配器实现 `PropertySystemAdapter`，不得将供应商字段泄漏到 Agent、页面或领域服务。
5. 使用真实脱敏测试集重新评测意图、字段、风险召回和 RAG 指标，并通过独立用户试用后，才讨论受控写入。
