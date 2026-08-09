# 阶段 5 可执行验收报告

以 `artifacts/` 下本机实际生成的 JSON 为准；`NOT_RUN` 不计为通过。推荐顺序：

```powershell
python scripts/run_test_suite.py
python evals/stage5/run.py
python scripts/run_performance_baseline.py
python scripts/run_e2e.py
python scripts/run_security_scan.py
python scripts/build_release_package.py
python scripts/check_stage5.py
```

## 2026-08-09 复核结果

- 完整回归：43 passed，0 failed，0 skipped。
- 独立离线评测：意图 20、抽取 6、高风险 10、提示词注入 10、参数校验 8、权限 4；全部阈值通过，抽取 F1 为 0.9286。
- 浏览器 E2E：3 条 API 安全/幂等检查及 3 条真实页面业务链路通过；页面链路覆盖居民建单、客服/维修/居民流转和公告草稿/审核/发布。
- 并发烟测：10 并发、160 请求、0 失败，整体 P95 396.11 ms；仅作为本机 SQLite 回归基线，不代表生产容量。
- 安全：密钥命中 0、部署依赖已知漏洞 0、Trivy 文件系统和镜像 HIGH/CRITICAL 均为 0，已生成 CycloneDX SBOM。漏洞库在线更新受当前网络阻断，使用 60.1 小时缓存，未超过 7 天门禁。
- 容器：非 root 用户运行；空容器迁移、种子导入与 `/ready` 数据库/向量库检查通过。

最终是否 release-ready 只由提交后的发布清单、校验和与 `scripts/check_stage5.py` 的实际输出判定。
