"""Suite-wide isolation for database, vector store, files and checkpoints."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "tmp" / f"pytest-runtime-{uuid.uuid4().hex}"
RUNTIME.mkdir(parents=True, exist_ok=False)

# These values must be set before test modules import api.config/api.database.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{(RUNTIME / 'test.db').as_posix()}"
os.environ["RAG_CHROMA_PATH"] = str(RUNTIME / "chroma")
os.environ["RAG_STORAGE_PATH"] = str(RUNTIME / "knowledge")
os.environ["AGENT_CHECKPOINT_PATH"] = str(RUNTIME / "agent-checkpoints.sqlite")
os.environ["HARNESS_FAILURE_INJECTION"] = ""


@pytest.fixture(scope="session", autouse=True)
def isolated_seeded_runtime():
    from data.seed import seed

    seed()
    yield RUNTIME
    shutil.rmtree(RUNTIME, ignore_errors=True)
