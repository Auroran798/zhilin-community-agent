install:
	python -m pip install -e ".[dev]"
migrate:
	alembic upgrade head
seed:
	python -m data.seed
knowledge-seed:
	python scripts/import_knowledge.py
rag-rebuild:
	python scripts/rebuild_rag_index.py
rag-sync-announcements:
	python scripts/sync_published_announcements.py
rag-eval-data:
	python evals/rag/generate_dataset.py
rag-eval:
	python evals/rag/run.py
rag-purge-logs:
	python scripts/purge_rag_logs.py
check:
	python -m alembic upgrade head
	python -m pytest -q
api:
	uvicorn api.main:app --reload
web:
	streamlit run web/app.py
test:
	pytest
stage5-test:
	python scripts/run_test_suite.py
coverage:
	pytest --cov=api --cov=domain --cov=data
compose-build:
	powershell -ExecutionPolicy Bypass -File scripts/compose_ascii_worktree.ps1 -Action build
compose-up:
	powershell -ExecutionPolicy Bypass -File scripts/compose_ascii_worktree.ps1 -Action up
compose-down:
	powershell -ExecutionPolicy Bypass -File scripts/compose_ascii_worktree.ps1 -Action down
agent-seed:
	python scripts/seed_agent_cases.py
agent-eval:
	python scripts/run_agent_eval.py
agent-check:
	python -m alembic upgrade head
	python scripts/check_agent.py
stage5-eval:
	python evals/stage5/run.py
stage5-performance:
	python scripts/run_performance_baseline.py
stage5-security:
	python scripts/run_security_scan.py
stage5-e2e:
	python scripts/run_e2e.py
stage5-screenshots:
	python scripts/capture_demo_screenshots.py
stage5-check:
	python scripts/check_stage5.py
release-package:
	python scripts/build_release_package.py
demo-up:
	docker compose up --build -d
demo-down:
	docker compose down
demo-reset:
	python scripts/reset_demo.py
	python -m alembic upgrade head
	python -m data.seed
	python scripts/import_knowledge.py
data-research:
	python -m scripts.stage6_pipeline research
data-download:
	python -m scripts.stage6_pipeline download
data-profile:
	python -m scripts.stage6_pipeline profile
data-normalize:
	python -m scripts.stage6_pipeline normalize
data-import:
	python -m scripts.stage6_pipeline import
data-check:
	python -m scripts.stage6_pipeline profile
	python -m scripts.stage6_pipeline evaluate
stage6-report:
	python -m scripts.stage6_pipeline report
stage6-pipeline:
	python -m scripts.stage6_pipeline all
postgres-up:
	docker compose -f docker-compose.yml -f docker-compose.public-real.yml up -d postgres
postgres-migrate:
	powershell -NoProfile -Command "$$env:DATA_MODE='public_real'; $$env:DATABASE_URL='postgresql+psycopg://zhilin:zhilin-local-dev-only@localhost:5432/zhilin'; .\.venv\Scripts\python.exe -m alembic upgrade head"
public-real-up:
	docker compose -f docker-compose.yml -f docker-compose.public-real.yml up --build -d
public-real-test:
	set DATA_MODE=public_real&& pytest tests/test_stage6_public_real.py -q
stage6-test:
	pytest tests/test_stage6_public_real.py tests/test_stage6_pipeline.py tests/test_stage6_readonly_integration.py -q
stage6-check:
	python -m scripts.stage6_pipeline profile
	python -m scripts.stage6_pipeline evaluate
	python -m scripts.stage6_pipeline report
