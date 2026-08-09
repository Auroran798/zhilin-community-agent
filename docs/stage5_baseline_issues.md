# Stage 5 baseline issues

| Check | Actual result | Blocking status | Resolution / retest |
|---|---|---|---|
| System Python | 3.14.0, project tests execute | Warning: project declares 3.12–3.14 and 3.14 works on this host | Regression run: 25 passed |
| Project `.venv` | Python 3.13, no installed dependencies | Non-blocking for this host; not used for validation | Use `python -m pip install -e ".[dev]"` in a clean environment |
| Alembic / seed / RAG | Upgrade, idempotent seed and local index rebuild succeeded | No | Rebuilt before browser E2E |
| Docker Compose rebuild | Direct Chinese-path build fails in Docker Desktop BuildKit | Resolved for Demo | ASCII worktree build completed; API :18019 and web :18519 both healthy |
| Playwright runtime | Package installed; bundled browser and ffmpeg unavailable | Partial | Browser E2E uses installed Chrome; video remains not generated without Playwright ffmpeg |
| Dependency scan | Global Python environment contained unrelated vulnerable packages | Release gate warning | Report retained; run in a clean, pinned project environment before a release claim |
| Trivy | 0.72.0 installed; config/secret scans completed | Partial external-network blocker | Vulnerability DB download failed from mirror.gcr.io, ghcr.io and Docker Hub; raw reports retained |
