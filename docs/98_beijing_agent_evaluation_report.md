# 北京物业 Agent 评测报告

执行日期：2026-08-10  
命令：`python scripts/run_agent_eval.py`、`python evals/beijing/run_controlled.py`、`python evals/beijing/run_security_gate.py`

## 回归结果

| 集合 | 数量 | 实测结果 |
| --- | ---: | --- |
| Agent 离线分类回归 | 95 | 意图准确率 1.0000；工具选择准确率 1.0000；风险识别准确率 1.0000 |
| 北京受控中英文回归 | 360 | 360/360 通过；pass rate 1.0000；jurisdiction 泄漏 0 |
| 北京安全门禁 | 5 组实测检查 | PASS；permission 泄漏 0；jurisdiction 泄漏 0 |

360 条集合由脚本自动生成，每个类别 24 条，共 15 类：全国规定、北京规定、小区合同规约、全国+北京适用链、上下位冲突、失效版本、北京/上海混问、北京/外国混问、证据不足、越权、提示词注入、无真实数据、中文问北京原文、英文问中国规定和同义改写。它明确是 `auto_generated_regression_not_gold`，未经独立人工审阅，不能称为正式金标。

机器明细见 [latest_controlled_results.json](../evals/beijing/latest_controlled_results.json)、[latest_security_results.json](../evals/beijing/latest_security_results.json)和 `evals/agent/reports/latest.json`。

## 已验证的行为

- 默认产品模式为 `domestic_beijing`，但全国问题只使用全国来源。
- 北京问题使用全国 + 北京适用链；当前小区问题再加入社区合同或规约。
- 国际问题进入 `international_research`，且一次只选择一个辖区。
- 国内模式不把英国、澳大利亚、新西兰或 Open311 资料作为北京依据。
- 查询账单、工单、投诉和房屋时只读取 Demo 或未来明确授权的数据。
- 居民跨房屋读取被拒绝；跨社区 RAG 没有泄漏。
- 提示词注入被阻断；赔偿、费用减免、账单修改和法律责任结论被拒绝。
- Agent 写操作面不包含公告发布、费用减免、账单修改或法律责任认定。

## 没有由分类评测测量的指标

`run_agent_eval.py` 不执行真实工具和写事务，因此以下指标明确为 `NOT_MEASURED`：slot extraction、真实工具调用成功率、确认门准确率、幂等成功率、在线权限隔离率、RAG 答案状态准确率和引用合规率。相关实现由 pytest 与北京安全门禁覆盖，但两者不能冒充真实端到端生产指标。

## 结论边界

当前结果证明受控路由、拒答和工具面回归稳定，不证明真实物业环境中的业务准确率、法律判断能力、模型泛化能力或生产可用性。正式 Agent 金标需要独立领域审阅者、真实但合规脱敏的查询分布、工具沙箱执行、跨角色端到端测试和失败恢复演练。
