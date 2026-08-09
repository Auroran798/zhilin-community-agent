# 阶段 5 浏览器 E2E 报告

仅 `browser_business_flow` 表示经页面完成的业务操作；API 检查单独标识。

```json
{
  "status": "PASS",
  "isolation": "temporary database, files, vector store and checkpoint",
  "scenarios": [
    {
      "name": "four roles authenticate",
      "evidence_type": "api_integration",
      "status": "PASS"
    },
    {
      "name": "cross-property bill access is denied",
      "evidence_type": "api_integration",
      "status": "PASS"
    },
    {
      "name": "same scoped write is replayed once",
      "evidence_type": "api_integration",
      "status": "PASS"
    },
    {
      "name": "resident creates a repair in UI",
      "evidence_type": "browser_business_flow",
      "status": "PASS"
    },
    {
      "name": "service-maintenance-resident lifecycle in UI",
      "evidence_type": "browser_business_flow",
      "status": "PASS"
    },
    {
      "name": "draft-review-publish announcement in UI",
      "evidence_type": "browser_business_flow",
      "status": "PASS"
    }
  ],
  "artifacts": [
    "resident_created_work_order.png",
    "work_order_completed.png",
    "announcement_published.png",
    "browser_business_trace.zip"
  ],
  "browser_business_flows": 3
}
```
