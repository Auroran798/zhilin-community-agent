# 北京物业智能体安全报告

执行日期：2026-08-10  
命令：`python scripts/run_security_scan.py`、`python evals/beijing/run_security_gate.py`

## 结论

本地安全门禁为 PASS：未发现 HIGH/CRITICAL 扫描项，受控权限泄漏和辖区泄漏均为 0。该结论只适用于本次代码、依赖解析结果和已扫描镜像/配置，不等于第三方渗透测试或生产安全认证。

| 检查 | 结果 |
| --- | --- |
| Secret pattern | 0 项，PASS |
| Bandit | LOW 2、MEDIUM 0、HIGH 0、CRITICAL 0，策略 PASS |
| pip-audit 已解析运行时依赖 | 0 项，PASS |
| Trivy 文件系统配置/秘密 | HIGH/CRITICAL 0，PASS |
| Trivy 镜像秘密 | HIGH/CRITICAL 0，PASS |
| Trivy 文件系统漏洞 | HIGH/CRITICAL 0，PASS |
| Trivy 镜像漏洞 | HIGH/CRITICAL 0，PASS |
| CycloneDX 镜像 SBOM | 已生成，PASS |
| Docker Compose 配置 | 可解析，PASS |
| 北京权限/辖区安全门 | permission leakage 0；jurisdiction leakage 0；PASS |

完整机器报告见 [stage5_security_summary.json](../artifacts/security/stage5_security_summary.json)。

## 业务安全控制

- 读操作按角色、房屋绑定、当前社区和数据授权过滤。
- 写操作保留 RBAC、Pydantic 参数校验、显式确认、幂等键和审计日志。
- Agent 不能自动发布公告、减免费用、修改账单或作出法律责任结论。
- 公告草稿可由 Agent 创建，但发布仍在经理人工 API 工作流。
- RAG 在召回前过滤模式、辖区、权限、审核、回答许可、版本和有效期。
- 外国资料与北京模式隔离；跨国家/城市混问拒答。
- Prompt injection 和越权指令在检索/工具执行前阻断。
- 合成数据不含真实个人信息，不把公开聚合统计写成小区个案。

## 扫描限制与警告

本次 Trivy 在线漏洞库更新因镜像站网络连接失败，最终统一验收使用了约 84.6 小时的本地缓存库。报告记录了这一警告；“缓存扫描通过”不能等同于“使用最新漏洞库通过”。正式发布前应在可联网环境更新 Trivy DB 后重跑，并安排独立渗透测试、密钥管理检查、生产权限审计、备份恢复和事件响应演练。

## 最终提交镜像补充扫描

2026-08-11 对最终离线镜像 `zhilin-beijing:2026.08.11-amd64` 追加执行 Trivy 镜像漏洞与秘密扫描。使用的缓存漏洞库更新时间为 2026-08-07，扫描退出码为 0；HIGH 0、CRITICAL 0、secret 0。完整 JSON 位于提交包 `evidence/submission_image_trivy.json`。

该补充结果只说明在该缓存数据库和所选扫描器范围内没有发现阻断项；不表示漏洞库最新，不替代第三方渗透测试、运行时防护、生产配置审计或安全认证。
