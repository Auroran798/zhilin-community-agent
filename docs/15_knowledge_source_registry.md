# 知识来源登记

来源登记表位于 `data/knowledge/source_registry.csv`，包含官方公开文件与“智邻花园”虚拟制度。官方文件直接从住房和城乡建设部、国务院、财政部和上海市房屋管理局的公开页面下载，且记录 URL、发布单位、获取日期、版本、生效日期、效力状态、适用地域和文件哈希。虚拟文件一律标记 `synthetic_community_document`，只适用于 `Demo Garden`，不作为真实物业承诺或普遍法律依据。

上海市文件仅在居民所属小区/区域为上海或用户明确询问上海规则时才应作为适用依据；不能作为全国规则。已发布公告由 `scripts/sync_published_announcements.py` 和公告发布接口同步，保留原公告 ID（`source_business_id`）。

公告仅在 `published` 状态创建 RAG 文档；撤回时同步标为 `inactive`，带 `end_time` 的公告在查询过滤时会自动排除。公告内容变更后重新发布会生成新的可追溯索引版本，并将旧索引标为 `superseded`。
