# 阶段 2 数据模型与保留策略

`knowledge_document` 是可检索资料的主记录，保存来源类型、来源 URL、发布单位、适用地域/小区、版本、生效/失效日期、文件与内容哈希、业务源 ID 和生命周期状态。`knowledge_document_version` 保留每个文件版本的哈希、存储位置、有效期与变更说明；相同文件不覆盖旧版本。

`knowledge_section`、`knowledge_chunk` 保存解析后的章节、条款路径、Chunk 顺序、向量标识、模型名、元数据和可疑内容标记。Chroma 只存向量与非敏感元数据，SQLite 是授权、版本和审计的事实来源。

`knowledge_ingestion_job` 记录索引任务状态、当前步骤、Chunk 数量、错误代码与错误摘要。`rag_query_log` 保存脱敏问题、作用域过滤、模型、检索 Chunk ID、答案哈希、引用数、耗时和错误码；`rag_feedback` 与查询日志关联，允许居民提交有用/无用反馈。

保留规则：源文件和版本不因重建而删除；撤回、过期、被替代资料仅退出默认检索范围；查询问题先脱敏后记录。生产环境应按 `RAG_QUERY_LOG_RETENTION_DAYS` 定期清理已到期的查询日志及其反馈，并保留聚合指标和审计记录。
