# 智邻管家｜北京物业智能体免 Docker 最终提交版

本提交包适用于 **Windows 10/11 64 位（x64/amd64）**，自带便携 Python 3.13、项目运行依赖、完整源码、受控知识资料、验收文档和机器证据。对方电脑无需安装 Docker，也无需预装 Python、数据库或向量库。

默认产品模式为 `domestic_beijing`；国际资料只在 `international_research` 中隔离使用；所有物业业务记录均为 `DEMO_SYNTHETIC`，不代表真实居民、账单、工单、小区或物业公司。

## 最简单的启动方法

1. 完整解压 ZIP，不要直接在压缩包里运行。
2. 双击根目录的 `一键启动-Windows.bat`。
3. Windows 如弹出防火墙提示，只需允许本机专用网络访问；程序默认只监听 `127.0.0.1`，不会向局域网公开。
4. 第一次启动会迁移数据库、生成 Demo 数据并建立知识索引，通常需要 2—8 分钟。
5. 启动成功后浏览器会打开 <http://127.0.0.1:8501>。

也可以在本目录打开 PowerShell 后执行：

```powershell
powershell -ExecutionPolicy Bypass -File ".\一键启动-Windows.ps1"
```

## 演示账户

所有账户密码均为 `DemoPass123!`。

| 角色 | 用户名 |
|---|---|
| 居民 | `resident_demo` |
| 客服 | `service_demo` |
| 维修 | `maintenance_demo` |
| 经理 | `manager_demo` |

## 运行检查

双击 `运行检查-Windows.bat`，或执行：

```powershell
powershell -ExecutionPolicy Bypass -File ".\运行检查.ps1"
```

最后出现以下文字即表示正常：

```text
PASS：便携 Python、API、离线 RAG、默认北京模式、数据边界和 Web 均正常。
```

## 停止服务

双击 `停止服务-Windows.bat`，或执行：

```powershell
powershell -ExecutionPolicy Bypass -File ".\停止服务-Windows.ps1"
```

普通停止不会删除 `runtime_data/` 中的演示数据。再次启动会继续使用此前产生的演示记录。

## 端口被占用

默认 Web 端口为 `8501`，API 端口为 `8000`。如果被其他程序占用，可执行：

```powershell
powershell -ExecutionPolicy Bypass -File ".\一键启动-Windows.ps1" -ApiPort 18080 -WebPort 18501
powershell -ExecutionPolicy Bypass -File ".\运行检查.ps1" -ApiPort 18080 -WebPort 18501
```

此时页面地址为 <http://127.0.0.1:18501>。

## 文件说明

- `runtime/`：便携 Python 3.13 与运行依赖，请勿删除或单独移动。
- `source/`：完整净化源码、受控知识资料、合成数据和迁移脚本。
- `runtime_data/`：首次启动后生成的数据库、索引、日志和 PID 信息。
- `documents/`：与 Docker 交付版相同的解决方案、验收、数据卡、评测、安全和完整功能验证文档。
- `evidence/`：机器可读验收、RAG、Agent、安全与便携运行验证结果。
- `checksums.sha256`：提交包内文件的 SHA-256；运行后 `runtime_data/` 会产生新文件，不属于初始校验清单。

## 系统要求和边界

- 只验证 Windows 10/11 x64；不支持直接在 macOS、Linux、Windows ARM 或 32 位 Windows 上运行。
- 建议至少 8 GB 内存和 5 GB 可用磁盘空间。
- 便携运行时来自本次验收使用的 CPython 3.13.14 x64 环境。
- 当前没有真实物业数据授权，业务数据全部是合成演示数据。
- 离线知识检索使用 `hashing-v1 + lexical-v1`，属于 `offline_fallback`，不得宣称正式多语种模型质量。
- 国际制度只作比较研究，不能作为北京物业处理依据。
- 系统不能自动发布公告、减免费用、修改真实账单或作出具体法律责任结论。
- 本包是课程/验收演示交付，不等同于生产部署、安全认证或真实物业上线。

详细步骤见根目录的 `免Docker运行操作说明.txt`，完整业务验收见 `documents/智能体完整功能验证文档.pdf`。
