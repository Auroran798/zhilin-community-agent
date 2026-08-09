# 阶段 2 导入、索引与运维

导入顺序为：登记来源 → 下载或制作文件 → `python scripts/import_knowledge.py` → 解析/清洗 → 分章节/分块 → 写入 SQLite 与 Chroma → 管理员审核激活。失败任务保留错误码，不会把半成品暴露给居民。

支持 PDF、DOCX、TXT、Markdown、HTML。扫描 PDF 没有可抽取文本时任务明确报 `ocr_required`；须经 OCR 后重新上传。导入工具按 SHA-256 去重，保留 URL、发布单位、获取日期；官方资料还应保存版本、生效日和效力状态。

日常命令：`make migrate`、`make knowledge-seed`、`make rag-rebuild`、`make rag-sync-announcements`、`make test`。公告由发布接口触发同步：草稿/待审不会同步，撤回为 `inactive`，结束时间已到自动排除，更新会产生新版本并将旧版本标为 `superseded`。

`/health` 仅表示进程存活；`/ready` 同时检查数据库和 Chroma。容器通过 `./data:/app/data` 持久化 SQLite、原文件、Chroma 索引和公告镜像，重启不丢数据。
