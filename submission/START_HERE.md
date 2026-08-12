# 智邻管家｜北京物业智能体最终提交版

本提交包同时提供离线 Docker 运行包、完整源码、验收文档、机器可读证据和 SHA-256 校验和。默认产品模式为 `domestic_beijing`；国际资料只在 `international_research` 中隔离使用；物业业务数据为 `DEMO_SYNTHETIC`，不代表真实居民、小区、账单、工单或物业公司事实。

## 1. 推荐运行环境

- Windows 10/11（64 位）+ Docker Desktop，或常见 x86_64 Linux + Docker Engine/Compose v2。
- CPU 架构：x86_64/amd64。Apple Silicon 或 Windows ARM 可尝试 Docker 的 amd64 模拟，但速度和兼容性不作为本提交包已验证范围。
- 建议至少 8 GB 内存、10 GB 可用磁盘空间。
- 首次导入离线镜像及初始化通常需数分钟；初始化完成后可断网运行。
- 默认端口：Web `8501`，API `8000`。端口被占用时，请先关闭占用程序。

Docker 是本运行方式的唯一前置软件。对方电脑也必须安装并启动 Docker；无需另装 Python、数据库、向量库或项目依赖。

## 2. 校验提交包

在本目录打开 PowerShell：

```powershell
Get-Content -Encoding UTF8 .\checksums.sha256 | ForEach-Object {
  if ($_ -match '^([0-9a-f]{64})  (.+)$') {
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $Matches[2]).Hash.ToLower()
    if ($actual -ne $Matches[1]) { throw "校验失败：$($Matches[2])" }
  }
}
"全部文件校验通过"
```

Linux 可运行：

```bash
sha256sum --check checksums.sha256
```

## 3. Windows 一键启动

1. 安装并打开 Docker Desktop，等到界面显示 Docker 正在运行。
2. 在提交包根目录打开 PowerShell。
3. 执行：

```powershell
powershell -ExecutionPolicy Bypass -File ".\一键启动-Windows.ps1"
```

脚本会检查 Docker、从 `docker/zhilin-beijing-amd64.tar` 导入离线镜像、启动 API/Web/后台任务，并等待知识库完成首次初始化。成功后自动打开 <http://127.0.0.1:8501>。

## 4. Linux 一键启动

```bash
chmod +x 一键启动-Linux.sh 停止服务-Linux.sh
./一键启动-Linux.sh
```

然后访问 <http://127.0.0.1:8501>。API 文档位于 <http://127.0.0.1:8000/docs>。

## 5. 演示账户

所有账户密码均为 `DemoPass123!`。

| 角色 | 用户名 | 主要验证内容 |
|---|---|---|
| 居民 | `resident_demo` | 本人房屋、报修、工单、账单、公告、通知、智能问答 |
| 客服 | `service_demo` | 受理派单、费用核查、公告草稿、人工处理 |
| 维修 | `maintenance_demo` | 工单处理、巡检记录、整改任务、设备历史 |
| 经理 | `manager_demo` | 看板、审核发布、巡检整改、审计、知识库治理 |

## 6. 自动运行检查

服务启动后，在 Windows PowerShell 执行：

```powershell
powershell -ExecutionPolicy Bypass -File ".\运行检查.ps1"
```

检查项包括容器状态、API、离线 RAG、登录、默认北京模式、真实数据授权边界和 Web 健康状态。完整的人工验收步骤见 `documents/智能体完整功能验证文档.pdf`。

## 7. 停止服务

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File ".\停止服务-Windows.ps1"
```

Linux：

```bash
./停止服务-Linux.sh
```

停止不会删除演示数据卷。再次启动会保留已产生的演示工单和操作记录。

## 8. 目录说明

- `docker/`：Compose 编排文件和可离线导入的 amd64 镜像。
- `source/`：可审计、可重新构建的完整净化源码；不包含本机数据库、缓存、虚拟环境和密钥。
- `documents/`：解决方案、验收、知识目录、数据卡、评测、安全和人工验证文档。
- `evidence/`：机器可读的最终验收、RAG、Agent/安全结果。
- `checksums.sha256`：提交包内全部文件（自身除外）的 SHA-256。

## 9. 已知边界

- 当前没有真实物业公司的数据授权，所有居民、房屋、工单、投诉、账单、巡检、设备和公告业务数据均为合成演示数据。
- `OPS_PUBLIC` 只用于公开聚合趋势分析，不作为任何个案事实。
- 离线检索使用确定性的 `hashing-v1 + lexical-v1` 回退配置；不得称为正式多语种语义质量或生产模型服务。
- 国际制度仅供比较研究，不能作为北京物业处理依据。
- 智能体不自动发布公告、不减免费用、不修改真实账单，也不作具体赔偿或法律责任承诺。
- 提交包是课程/验收演示交付，不等同于已经完成生产部署、等保测评或真实业务上线。

## 10. 常见故障

- “Docker 引擎未运行”：打开 Docker Desktop，等待其完全启动后重试。
- “端口已被占用”：关闭占用 `8000` 或 `8501` 的程序；也可由技术人员设置 `API_PORT`/`WEB_PORT` 后用 Compose 启动，但前端默认访问地址相应改变。
- 首次启动等待较久：API 正在迁移数据库、生成 Demo 数据并重建离线知识索引，可运行 `docker compose -f docker/docker-compose.submit.yml logs -f api` 查看进度。
- 页面无法打开：先运行 `运行检查.ps1`，再查看 `docker compose -f docker/docker-compose.submit.yml ps` 和容器日志。
- 需要完全重置：`docker compose -f docker/docker-compose.submit.yml down -v` 会永久删除提交版演示数据卷；只有明确需要清空演示数据时才执行。
