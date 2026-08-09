# 阶段 6 完成报告：真实公开业务数据模式

完成时间：2026-08-07（Asia/Shanghai）

## 结论

阶段 6 已完成可运行的真实公开数据链路。系统实际接入的是美国纽约市 Department of Housing Preservation and Development (HPD) 发布的历史住宅维护监管数据；它们不是中国物业公司生产数据，也不表示任何地址的当前状态。

- 真实历史报修/投诉案例：50,000 条，来自 `ygpa-z7cr`。
- 真实检查/违规整改案例：10,000 条，来自 `wvxf-dwi5`；该数据集说明违规通常由房屋检查员现场检查后签发（一般行政签发的 Class I 例外）。
- SQLite Demo 数据模式保留；`DATA_MODE=public_real` 启用独立的公共真实数据模式。
- 已增加 PostgreSQL 驱动、迁移和 Compose 覆盖文件；SQLite 数据库已实际迁移并导入 60,000 条记录。

## 经过核实的候选数据

| Dataset | 国家 | 官方机构 | 核实规模/字段 | License / 条款 | 本次下载 | 评分 | 采用 |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| Seattle Code Complaints and Violations (`ez4a-iug7`) | US | Seattle Department of Construction & Inspections | 244,232 / 17 | Public Domain | 否，运行环境直连 API 返回 403 | 84.3 | 否 |
| SF Fire Inspections (`wb4c-6hwj`) | US | San Francisco Fire Department / DataSF | 门户 37 列 | ODC PDDL | 否，运行环境直连 API 返回 403 | 81.4 | 否 |
| SF Fire Violations (`4zuq-2cbe`) | US | San Francisco Fire Department / DataSF | 门户 24 列 | ODC PDDL | 否，运行环境直连 API 返回 403 | 83.0 | 否 |
| NYC HPD Complaints and Problems (`ygpa-z7cr`) | US | NYC HPD | 16,227,351 / 34 | NYC Open Data terms | 50,000 | 92.0 | 是，公共真实工单案例 |
| NYC HPD Housing Maintenance Code Violations (`wvxf-dwi5`) | US | NYC HPD | 11,150,614 / 35 | NYC Open Data terms | 10,000 | 93.1 | 是，公共真实检查/整改案例 |
| Chicago Building Violations (`22u3-xenr`) | US | City of Chicago Department of Buildings | 2,021,952 / 26 | 数据集页标为 unspecified | 否 | 76.0 | 否，许可证不明确 |

完整字段、访问、评分与拒绝理由见 `data/source_research/dataset_candidates.csv`。Source Registry 见 `data/public_real/source_registry.csv`。

## 实际数据处理结果

| 数据集 | 原始/下载 | 清洗后 | 去重后 | 脱敏规范化 | 映射成功 | 未映射 | 首次导入 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| NYC HPD Complaints | 50,000 | 50,000 | 50,000 | 50,000 | 50,000 | 0 | 50,000 |
| NYC HPD Violations | 10,000 | 10,000 | 10,000 | 10,000 | 10,000 | 0 | 10,000 |
| 合计 | 60,000 | 60,000 | 60,000 | 60,000 | 60,000 | 0 | 60,000 |

第二次导入验证为 `created=0, updated=60,000`，证明 `(source_dataset_id, source_record_id)` 唯一约束和导入器具备幂等性。

下载使用官方 SODA API、无账号、无爬虫、无 CAPTCHA 绕过。为避免首 N 行偏差，使用固定种子随机偏移采样：投诉 10 页、违规 3 页，清单中记录页数、SHA-256、字段选择与检索时间。原始文件是不可覆盖 JSONL；Git 忽略完整 raw/processed/normalized 文件。

## 数据质量与隐私

| 指标 | Complaints | Violations |
| --- | ---: | ---: |
| 原始字段 | 20 | 15 |
| 原始重复 source ID | 0 | 0 |
| 时间范围 | 2003-12-04 至 2026-07-29 | 1974-04-16 至 2026-08-05 |
| 原始文本均长 / 中位数 | 230.49 / 210 | 197.00 / 185 |
| 规范化层 PII 模式命中 | 0 | 0 |
| ZIP 前缀缺失率 | 0.082% | 0.050% |

API 查询时只请求最小化字段，排除街道、门牌、房号、经纬度、联系人和账号字段。`PrivacySanitizer` 会再替换电话、邮箱、单元/房号和街道地址模式。`public_cases` 业务表只保存 `sanitized_text`、粗粒度位置、来源字段名和不可逆原始行哈希；原文与完整载荷不进入业务表。Web/API/MCP/Agent 也不会返回原始文本、完整载荷、精确地址或坐标。原文保留英文于受控 raw 层，`original_language=en`、`translation_status=not_translated`，未把英文记录伪装为中文原始数据。

## 统一模型、数据库与接口

新增隔离的 `public_datasets` 与 `public_cases` 表，而非将外部监管记录伪装成虚拟住户工单。每条记录保存：`source_type`、国家、数据集、数据集 ID、来源记录 ID、来源 URL、许可证、获取时间、原始语言、翻译状态、规范化/映射版本、脱敏文本、来源字段名/原始行哈希、映射类别、风险、状态和实际时间字段。没有创建虚构住户、房屋绑定、账单、派单、维修人员或满意度。

- 迁移：`20260807_stage6_public_real`；SQLite 当前为 head。
- 索引：来源数据集/记录唯一约束、数据集+记录种类+发生时间复合索引，以及类别、状态、风险和粗粒度位置索引。
- API：`GET /api/v1/public-real/datasets`、`/summary`、`/cases`、`/cases/{id}`；仅客服和管理员，`DATA_MODE=public_real` 时可用。
- Agent：新增 `public_real_case_query`，识别“真实公开案例”等意图；只返回脱敏历史记录。
- MCP：新增只读 `search_public_real_cases`；Harness 标记 `operation_type=read`，客服/管理员角色校验、审计和调用链均生效。
- Web：管理端和客服端新增“真实公开案例”页；管理看板在 Public Real 模式含独立的公开数据统计，绝不混入租户工单指标。

## 映射评测、联调与回归

- 原 320 条评测由待测规则自行生成期望标签，存在循环验证，已作废并保留为
  `evals/stage6/category_mapping_legacy_rule_generated.jsonl` 历史证据。当前评测状态为
  `NOT_RUN`；只有完成不少于 300 条独立人工标注并生成
  `evals/stage6/category_mapping_gold.jsonl` 后，发布门禁才接受映射准确率。
- 真实数据模式 API：实际返回 `total=60,000`，管理端可查询；响应不包含原始文本或 payload。
- Agent 烟测：管理端查询真实公开历史案例，识别意图 `public_real_case_query`，返回 20 条脱敏案例。
- MCP/Harness 烟测：`search_public_real_cases` 返回 3 条消防设施案例，trace ID 已写入调用链；工具为只读。
- API 启动检查：本地 `/health` 返回 `{"status":"ok"}`；Web Streamlit 健康检查返回 `ok`。公共真实 Compose 的 `config --quiet` 通过，PostgreSQL 16 容器实际达到 `healthy`，迁移至 `20260807_stage6_public_real` 并导入 2 个数据集、60,000 条案例；使用 PostgreSQL 的受控 `/api/v1/public-real/summary` 返回 200。
- 全量 pytest：37 passed，0 failed，0 skipped。阶段分组为：阶段 1 6、阶段 2 3、阶段 3 9、阶段 4 7、阶段 5 3、阶段 6 9，均通过。

## PostgreSQL 与运行方式

`pyproject.toml` 已声明 `psycopg[binary]`。Public Real Compose 覆盖位于 `docker-compose.public-real.yml`，包含 PostgreSQL、API、Web（继承基础 Compose）及可选 stdio MCP 服务：

```powershell
python -m scripts.stage6_pipeline research
python -m scripts.stage6_pipeline download
python -m scripts.stage6_pipeline profile
python -m scripts.stage6_pipeline normalize
docker compose -f docker-compose.yml -f docker-compose.public-real.yml up -d postgres
# 设置 DATABASE_URL 到 PostgreSQL 后：
python -m alembic upgrade head
python -m data.seed
python -m scripts.stage6_pipeline import
docker compose -f docker-compose.yml -f docker-compose.public-real.yml up --build -d
```

使用 SQLite Public Real 模式：设置 `DATA_MODE=public_real`，执行 `python -m alembic upgrade head`、`python -m data.seed`、`python -m scripts.stage6_pipeline import` 后启动 API。设置 `DATA_MODE=demo` 即回到原有合成 Demo。

## 交付位置与已知例外

- 数据清单：`data/public_real/manifests/`；原始数据：`data/public_real/raw/`；处理中间层：`data/public_real/processed/`；规范化层：`data/public_real/normalized/`；脱敏样本：`data/public_real/samples/`。
- 质量画像：`artifacts/data_quality/`；质量/隐私报告：`docs/stage6_data_quality_report.md`；本报告：本文件。
- 映射：`data/mappings/external_category_mapping.csv`；重新下载/导入命令：`scripts/stage6_pipeline.py` 和 `Makefile` 的 `data-*` 目标。
- 现有 Stage 0—5 模型与迁移存在的 `alembic check` 漂移已在 `docs/stage6_baseline_issues.md` 如实记录；它不包含阶段 6 新表。
- Seattle/DataSF 数据的官方页面、字段和许可证已核实，但本次执行环境对其直连 API 返回 HTTP 403；未尝试绕过限制，也未使用非官方镜像替代。
