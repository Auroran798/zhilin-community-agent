# Docker deployment

```powershell
docker compose up --build -d
Invoke-WebRequest http://localhost:8000/ready
docker compose down
```

The API is exposed at `http://localhost:8000`, OpenAPI at `/docs`, and the web UI at `http://localhost:8501`. `docker compose config` validates the compose model. The Compose stack is a local Demo only.

## Chinese-path Docker Desktop workaround

On this Windows workstation Docker Desktop can fail when the source checkout path contains Chinese characters. Use the included one-command wrapper; it mirrors only build inputs to an ASCII path and then runs Compose there:

```powershell
.\scripts\compose_ascii_worktree.ps1 -Action build
.\scripts\compose_ascii_worktree.ps1 -Action up
Invoke-WebRequest http://localhost:18019/ready
Invoke-WebRequest http://localhost:18519/_stcore/health
```

The wrapper deliberately excludes generated artifacts and test temporary files, so an open pytest work directory cannot block a rebuild.
