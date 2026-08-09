# Phase 6 许可证与隐私合规报告

生成时间：2026-08-07（Asia/Shanghai）

## 数据使用边界

本项目只将公开数据用于非生产演示、质量评估和受控的历史案例检索；不将其描述为本小区真实业务，不反向识别个人，也不将原始记录暴露给普通用户。

| 数据集 | 发布方 | 许可证/使用条款 | 工程处理 |
|---|---|---|---|
| NYC HPD Complaints and Problems | NYC Department of Housing Preservation and Development | NYC Open Data 公共数据政策与数据集条款 | 仅拉取必要字段；原始层受忽略规则保护；业务层不返回原文或 source payload。 |
| NYC Housing Maintenance Code Violations | NYC Department of Housing Preservation and Development | NYC Open Data 公共数据政策与数据集条款 | 同上；用于现场检查/违规案例补充。 |

候选调研中的 Seattle、San Francisco 与 Chicago 数据集仅用于来源评估，未进入运行时数据层。

## 隐私处理措施

1. 下载阶段按字段白名单查询，不请求门牌号、街道、单元号、邮编、经纬度等地址定位字段。
2. 清洗阶段删除直接身份和精确地址键；文本执行邮箱、电话、身份证样式、房间/单元号、住址样式脱敏。
3. 规范化数据的 `source_text` 和 `address_area` 均只保留脱敏值；质量报告确认两个规范化文件的 PII 命中数为 0。
4. 业务数据库、API、MCP、Agent 与前端仅保留/返回已脱敏案例摘要；不会保存或返回原始描述、完整 source payload、精确地址或坐标。
5. 真实公开模式默认关闭（`DATA_MODE=demo`）；开放历史检索需 `DATA_MODE=public_real` 且为客服/经理角色，检索仅限审计友好的只读操作。

## 可追溯性与撤回

每条导入案例保存 `source_dataset_id`、`source_record_id`、原始字段名、不可逆原始行哈希、来源更新时间、拉取时间和转换版本。原始文件 SHA-256、行数、schema 与来源 URL 写入 manifest。若来源条款更新、数据撤回或出现合规风险，可停止拉取、清空 `public_cases`/`public_datasets` 后从已审查来源重新导入；该操作应由数据管理员按变更流程执行。
