# Third-party notices

## Stage 6 public data

- NYC Department of Housing Preservation and Development (HPD), *Housing Maintenance Code Complaints and Problems* (`ygpa-z7cr`) and *Housing Maintenance Code Violations* (`wvxf-dwi5`), accessed through NYC Open Data's documented SODA API. The system preserves the official source URL, dataset ID, retrieval time, terms URL and record ID for each imported public case. NYC Open Data states its datasets are available without registration, license requirement or usage restrictions under the Open Data Law, while NYC.gov Terms of Use and any agency-specific terms continue to apply. Data are informational, can change, and carry no warranty. These US historical regulatory records are not Chinese property-management records, legal advice, or current-condition assertions.

## Stage 5 tooling research (2026-08-05)

- Playwright Python — Apache-2.0; optional development dependency for browser E2E, traces, screenshots and video. No upstream code is copied.
- Locust — MIT; evaluated as a future concurrent-load runner and not added because the Stage 5 baseline uses a smaller repeatable local measurement.
- Promptfoo — MIT; evaluated as an optional LLM red-team runner and not added because deterministic security regression cases remain the acceptance baseline.
- Ragas — Apache-2.0; evaluated as an optional RAG metric helper and not added because this offline Demo has deterministic retrieval/citation tests.
- Trivy — Apache-2.0; optional external scanner invoked only when installed; no scanner code is bundled.

All direct Python dependencies are declared in `pyproject.toml`; external projects are design references only unless explicitly listed as dependencies.
本项目未复制 Condo、Atlas CMMS 或 FastAPI Full Stack Template 的源代码。依赖包通过 pyproject.toml 声明，并分别遵循其发布许可证。Atlas CMMS 为 AGPL-3.0，仅作为业务概念参考，不引入其代码或组件。
# 阶段 3

- LangGraph (https://github.com/langchain-ai/langgraph), MIT License, version range `>=1.2,<1.3`. Used as the single graph orchestration library.
- langgraph-checkpoint-sqlite, MIT License, version range `>=3.1,<4`. Used only for local SQLite checkpoints.
