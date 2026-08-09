# Stage 7 Docker 与 PostgreSQL 验收记录

验收日期：2026-08-08。

## 构建修复

- `.dockerignore` 排除 pytest 临时测试目录，避免 Docker 无法遍历已受限的运行时目录；
- Dockerfile 将第三方运行依赖置于独立缓存层；
- 使用二进制优先安装、5 次重试、120 秒超时和可配置 `PIP_INDEX_URL`；默认使用清华 PyPI 镜像；
- 应用源码层使用 `--no-deps --no-build-isolation`，避免重复解析全部依赖。

首次依赖层构建成功，后续仅源码变更的重建复用了依赖层。

## 实际验收

1. Docker Desktop Engine `29.6.2`：可连接；
2. 基础 Compose：API `/ready` = 200，Web `/_stcore/health` = 200；
3. 隔离 PostgreSQL Compose：PostgreSQL、API、Web 均健康；
4. PostgreSQL：`alembic current` 为 `20260808_stage7_business_closure (head)`；
5. PostgreSQL：`alembic check` 输出 `No new upgrade operations detected.`；
6. 真实 HTTP：报修/SLA、公告提交-审批-发布、住户通知、Scheduler 调度均成功。

验收环境使用独立 Compose 项目与独立 PostgreSQL 卷，未删除既有公共数据卷。服务已使用 `docker compose down` 安全停止，卷保留用于复核。
