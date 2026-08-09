# Stage 5 integration architecture

```mermaid
flowchart LR
  R["Resident / staff / maintenance / manager"] --> W["Streamlit web"] --> A["FastAPI"]
  A --> G["LangGraph agent + Skills"]
  G --> K["RAG / Chroma"]
  G --> H["Harness: timeout, retry, redaction"]
  H --> M["MCP client / server"] --> D["Domain services"] --> S["SQLite"]
  A --> O["Audit, traces, metrics"]
  G --> C["User confirmation / human review"]
  T["Pytest + Playwright + deterministic evals"] --> A
  X["Docker Compose"] --> A
  X --> W
```

The diagram is intentionally limited to components in this repository. All state-changing tool paths remain subject to authorization, confirmation/idempotency and audit controls.
