# 智邻管家免 Docker 便携交付补充说明

生成日期：2026-08-12  
交付形式：Windows 10/11 x64 便携 ZIP  
总体状态：`PASS`

## 交付方式

免 Docker 版在 ZIP 中自带 CPython 3.13.14 x64、项目运行依赖、净化源码、受控知识资料、Demo 合成数据、SQLite/Chroma 本地运行配置、启动/停止/检查脚本，以及与 Docker 版相同的项目交付文档和证据。

对方无需安装 Docker，也无需预装 Python、数据库或向量库。完整解压后双击 `一键启动-Windows.bat` 即可；首次启动自动执行 Alembic、Demo 播种、82 项来源治理和知识索引导入。

## 实测结果

| 验收项 | 结果 |
| --- | --- |
| 便携 Python | CPython 3.13.14 x64；根目录自动迁移；PASS |
| 核心运行依赖 | FastAPI、Streamlit、SQLAlchemy、Chroma、Alembic、LangGraph、MCP、PDF/DOCX 解析全部导入；PASS |
| pip check | `No broken requirements found` |
| 全新 runtime_data 冷启动 | Alembic、Demo 播种、来源治理、知识导入全部 PASS |
| API / Web | `/ready=ready`；Web health HTTP 200 |
| 默认模式 | `domestic_beijing` |
| 数据授权标识 | `real_property_authorization=false` |
| 北京适用链 | 全国 + 北京；PASS |
| 全国问题 | 仅全国；PASS |
| 国际研究 | GB 精确隔离并显示比较研究警告；PASS |
| 北京 + 澳大利亚混问 | 拒答；`FOREIGN_SOURCE_REQUIRES_RESEARCH_MODE` |
| 启动/运行检查/停止 | PowerShell 实机 PASS |
| 持久化重启 | PASS |
| 独立路径迁移 | 完整包移动到新的英文路径、清空 runtime_data 后再次冷启动；PASS |

机器报告见 `evidence/nondocker_runtime_acceptance.json`。

## 与 Docker 版的差异

| 项目 | Docker 版 | 免 Docker 便携版 |
| --- | --- | --- |
| 前置软件 | Docker Desktop | 无；自带 Python |
| 支持范围 | linux/amd64 容器，可由 Windows/Linux Docker 承载 | Windows 10/11 x64 |
| 隔离方式 | 容器与命名卷 | 本地隐藏进程与 `runtime_data/` |
| 停止方式 | Compose down | PID 归属检查后停止便携 Python 进程 |
| 数据位置 | Docker 命名卷 | 解压目录的 `runtime_data/` |
| 防病毒影响 | 通常较少 | 便携 Python 可能需要安全软件放行 |

两种交付使用同一套源码、知识注册表、文档、数据边界和产品模式。免 Docker 版没有扩大系统能力或生产声明。

## 不能宣称的能力

- 不能声称已接入真实居民、真实账单、真实工单或真实物业公司系统。
- 不能把合成业务记录描述为真实数据。
- 不能把 `offline_fallback` 描述为正式多语种模型质量。
- 不能把国际资料作为北京物业处理依据。
- 不能承诺具体赔偿、自动减费、修改真实账单或认定法律责任。
- 不能把 Windows 便携验收说成 macOS、Linux、ARM 或生产环境兼容认证。
- 不能把本地端口和隐藏进程的运行方式说成生产级服务托管、高可用或安全认证。

## 提交建议

对方电脑如果可以安装 Docker，优先提交 Docker 版；如果对方不允许或不会安装 Docker，可提交本免 Docker Windows x64 便携版。提交时保留完整 ZIP，不要单独复制 `runtime/` 或 `source/`，也不要直接在 ZIP 内运行。
