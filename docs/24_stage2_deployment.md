# 阶段 2 部署与配置

复制 `.env.example` 为 `.env`，必须替换 JWT 密钥。默认 SQLite 适合本地演示；多人生产部署应切换受控数据库并将 `data` 挂载到备份卷。运行 `docker compose up --build` 后，API 为 8000、前端为 8501。

生产配置真实嵌入时填写 `RAG_EMBEDDING_PROVIDER`、`RAG_EMBEDDING_MODEL`、`RAG_EMBEDDING_API_BASE`、`RAG_EMBEDDING_API_KEY`。密钥只通过密钥管理或环境注入，不写入 CSV、日志和代码。若向量库不可用，`/ready` 返回非就绪，部署编排不得将实例接流量。

发布检查：迁移成功、`/ready` 为 ready、官方登记字段完整、虚拟资料有 synthetic 标识、公告同步演练成功、80 条评测报告生成、权限/注入/跨小区测试通过，并检查数据卷可恢复。
