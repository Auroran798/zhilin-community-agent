from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "智邻管家"
    database_url: str = "sqlite:///./data/zhilin.db"
    # demo keeps synthetic tenant data; public_real exposes only the separate,
    # sanitized public-regulatory schema to authorised staff.
    data_mode: str = "demo"
    public_real_query_limit: int = 100
    jwt_secret: str = "development-only-change-this-secret-to-32-bytes"
    jwt_algorithm: str = "HS256"
    token_expire_minutes: int = 480
    demo_password: str = "DemoPass123!"
    sla_hours_p1: int = 4
    sla_hours_p2: int = 24
    sla_hours_p3: int = 72
    rag_enabled: bool = True
    rag_storage_path: str = "data/knowledge/files"
    rag_chroma_path: str = "data/knowledge/chroma"
    rag_collection_prefix: str = "property_kb"
    rag_index_schema_version: str = "2"
    rag_chunk_size: int = 700
    rag_chunk_overlap: int = 100
    rag_retrieval_top_k: int = 5
    rag_score_threshold: float = 0.12
    rag_final_context_k: int = 5
    rag_hybrid_enabled: bool = True
    rag_rerank_enabled: bool = True
    rag_embedding_provider: str = "hash"
    rag_embedding_model: str = "hashing-v1"
    rag_embedding_api_base: str | None = None
    rag_embedding_api_key: str | None = None
    rag_llm_provider: str = "disabled"
    rag_llm_model: str | None = None
    rag_llm_api_base: str | None = None
    rag_llm_api_key: str | None = None
    rag_query_log_retention_days: int = 30
    max_knowledge_file_size_mb: int = 10
    max_request_body_size_mb: int = 10
    agent_enabled: bool = True
    agent_llm_provider: str = "fake"
    agent_llm_model: str | None = None
    agent_llm_api_base: str | None = None
    agent_llm_api_key: str | None = None
    agent_llm_timeout_seconds: int = 30
    agent_llm_max_retries: int = 1
    agent_max_history_messages: int = 20
    agent_max_follow_up_rounds: int = 3
    agent_confirmation_ttl_minutes: int = 30
    agent_long_term_memory_enabled: bool = True
    agent_checkpoint_path: str = "data/agent_checkpoints.sqlite"
    mcp_enabled: bool = True
    mcp_server_name: str = "property-community-agent"
    mcp_server_version: str = "1.3.0-remediation"
    mcp_transport: str = "stdio"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8011
    mcp_dev_auth_enabled: bool = False
    mcp_dev_user_id: str | None = None
    mcp_dev_session_token: str | None = None
    mcp_dev_write_confirmed: bool = False
    agent_tool_backend: str = "local"
    mcp_client_enabled: bool = False
    mcp_client_transport: str = "stdio"
    mcp_client_command: str | None = None
    mcp_client_url: str | None = None
    mcp_client_timeout_seconds: int = 15
    mcp_allow_local_fallback: bool = False
    harness_enabled: bool = True
    harness_default_timeout_seconds: int = 15
    harness_read_retries: int = 1
    harness_circuit_failure_threshold: int = 3
    harness_circuit_reset_seconds: int = 30
    harness_failure_injection: str | None = None
    # Stage 6 is opt-in: no upstream property-system data is read until a
    # partner, authorization and data-boundary review have been completed.
    stage6_readonly_integration_enabled: bool = False
    property_system_adapter: str = "demo"
    property_system_demo_data_path: str = "data/external_reference/demo_property_work_orders.json"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def reject_unsafe_production_settings(self):
        """Fail closed when a development-only setting reaches production."""
        if self.app_env.lower() not in {"production", "prod"}:
            return self
        weak_markers = ("development-only", "change-this", "changethis", "demo")
        if len(self.jwt_secret) < 32 or any(marker in self.jwt_secret.lower() for marker in weak_markers):
            raise ValueError("Production requires a strong JWT_SECRET of at least 32 characters")
        if self.demo_password == "DemoPass123!":
            raise ValueError("Production must not use the demo account password")
        if self.mcp_dev_auth_enabled or self.mcp_dev_write_confirmed:
            raise ValueError("Production must not enable MCP development authentication or global write confirmation")
        if self.mcp_allow_local_fallback:
            raise ValueError("Production must not silently fall back to the local tool backend")
        if self.harness_failure_injection:
            raise ValueError("Failure injection is test-only")
        return self

settings = Settings()
Path("data").mkdir(exist_ok=True)
