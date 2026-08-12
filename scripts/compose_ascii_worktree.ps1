[CmdletBinding()]
param(
    [ValidateSet("config", "build", "up", "down")]
    [string]$Action = "build",
    [string]$ProjectName = "zhilin-stage4-ascii",
    [int]$ApiPort = 18019,
    [int]$WebPort = 18519,
    [string]$PythonBaseImage = "mcr.microsoft.com/azurelinux/base/python:3.12"
)

# Docker Desktop BuildKit can reject a Compose build when the checkout path
# contains non-ASCII characters. Keep the source untouched and mirror it to an
# ASCII-only, script-owned worktree for Compose operations.
$source = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$worktree = "C:\DockerBuild\zhilin-community-agent"
if ($worktree -notmatch '^[\x00-\x7F]+$') {
    throw "Compose worktree path must contain ASCII characters only."
}

New-Item -ItemType Directory -Force -Path $worktree | Out-Null
$robocopyArgs = @(
    $source, $worktree, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP",
    "/XD", ".git", ".github", ".venv", ".pytest_cache", "artifacts", "tmp", "tmp_dockerdesktop_cn_4.84.0", "tmp_pdf_review", "zhilin_community_agent.egg-info", "__pycache__",
    "/XF", ".coverage"
)
& robocopy @robocopyArgs
if ($LASTEXITCODE -ge 8) {
    throw "Failed to mirror the source into $worktree (robocopy exit code $LASTEXITCODE)."
}

$previousLocation = Get-Location
try {
    Set-Location $worktree
    $env:API_PORT = "$ApiPort"
    $env:WEB_PORT = "$WebPort"
    $env:PYTHON_BASE_IMAGE = $PythonBaseImage
    switch ($Action) {
        "config" { & docker compose -p $ProjectName config --quiet }
        "build"  { & docker compose -p $ProjectName build api web }
        "up"     { & docker compose -p $ProjectName up -d }
        "down"   { & docker compose -p $ProjectName down }
    }
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $Action failed with exit code $LASTEXITCODE."
    }
} finally {
    Set-Location $previousLocation
}
