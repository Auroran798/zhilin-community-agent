# 阶段 5 安全扫描

```json
{
  "status": "PASS",
  "generated_at": "2026-08-09T14:08:55.854232+00:00",
  "checks": [
    {
      "name": "secret-pattern",
      "status": "PASS",
      "report": "artifacts\\security\\secrets.json",
      "findings": 0
    },
    {
      "name": "bandit",
      "status": "PASS",
      "returncode": 1,
      "counts": {
        "LOW": 2,
        "MEDIUM": 0,
        "HIGH": 0,
        "CRITICAL": 0
      },
      "report": "artifacts\\security\\bandit.json"
    },
    {
      "name": "pip-audit-resolved-runtime",
      "status": "PASS",
      "findings": 0,
      "report": "artifacts\\security\\dependencies\\pip_audit.json",
      "cached_within_hours": 24
    },
    {
      "name": "trivy-vulnerability-db",
      "status": "PASS",
      "source": "cached",
      "age_hours": 60.1,
      "update_warning": "rror\trun error: init error: DB error: failed to download vulnerability DB: OCI artifact error: failed to download vulnerability DB: failed to download artifact from mirror.gcr.io/aquasec/trivy-db:2: OCI repository error: 1 error occurred:\n\t* Get \"https://mirror.gcr.io/v2/\": dial tcp 142.250.99.82:443: connectex: A connection attempt failed because the connected party did not properly respond after a period of time, or established connection failed because connected host has failed to respond.\n\n\n"
    },
    {
      "name": "trivy-fs-config-and-secrets",
      "status": "PASS",
      "returncode": 0,
      "counts": {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "CRITICAL": 0,
        "UNKNOWN": 0
      },
      "report": "artifacts\\security\\trivy\\filesystem.json"
    },
    {
      "name": "trivy-image-secrets",
      "status": "PASS",
      "returncode": 0,
      "counts": {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "CRITICAL": 0,
        "UNKNOWN": 0
      },
      "report": "artifacts\\security\\trivy\\image-api.json"
    },
    {
      "name": "trivy-filesystem-vulnerabilities",
      "status": "PASS",
      "returncode": 0,
      "counts": {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "CRITICAL": 0,
        "UNKNOWN": 0
      },
      "report": "artifacts\\security\\trivy\\filesystem-vulnerabilities.json"
    },
    {
      "name": "trivy-image-vulnerabilities",
      "status": "PASS",
      "returncode": 0,
      "counts": {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "CRITICAL": 0,
        "UNKNOWN": 0
      },
      "report": "artifacts\\security\\trivy\\image-api-vulnerabilities.json"
    },
    {
      "name": "cyclonedx-image-sbom",
      "status": "PASS",
      "returncode": 0,
      "report": "artifacts\\security\\sbom\\image-api.cdx.json"
    },
    {
      "name": "docker-compose-config",
      "status": "PASS",
      "returncode": 0,
      "report": "artifacts\\security\\docker_compose_config.txt"
    }
  ],
  "critical": 0,
  "high": 0,
  "note": "NOT_RUN means a scanner was unavailable and is not interpreted as PASS. HIGH/CRITICAL findings fail the release gate and require remediation or a separately reviewed waiver."
}
```

文件系统、已构建 API 镜像和解析后的部署依赖均完成扫描；漏洞库来源与缓存年龄以 JSON 中 `trivy-vulnerability-db` 为准。完整明细保存在 artifacts/security。
