# 阶段 3 完成报告

本阶段新增单 LangGraph 总控图、Fake/OpenAI-compatible LLM Provider、风险规则、工具白名单、确认中断、会话/运行审计、人工转接、经授权长期记忆、FastAPI 接口和 Streamlit 对话页。居民可通过自然语言完成报修、查询/取消/评价工单、查询/解释账单和创建核查申请；客服可生成双版本公告草稿；巡检人员可提交异常并自动生成整改工单。高风险事件、账单修改、费用减免与公告发布均不会被智能体自动执行。阶段 4 的 MCP Server、Inspector、Harness 和多智能体协作未实现，也不作为本阶段能力宣称。

数据迁移为 `20260802_stage3_agent.py` 与 `20260802_stage3_full.py`；运行前执行 `python -m alembic upgrade head`。完整测试、评测和环境限制见阶段 3 测试/评测报告及基线问题文档。

若 Docker Hub 临时不可达，但本机已有本项目的基础镜像，可用 `Dockerfile.offline` 仅在本地重建；它不是 CI 或生产环境的替代品。
