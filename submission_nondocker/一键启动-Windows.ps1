[CmdletBinding()]
param(
    [ValidateRange(1, 65535)][int]$ApiPort = 8000,
    [ValidateRange(1, 65535)][int]$WebPort = 8501,
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $root "source"
$python = Join-Path $root "runtime\python.exe"
$runtimeData = Join-Path $root "runtime_data"
$logs = Join-Path $runtimeData "logs"
$pidFile = Join-Path $runtimeData "service-pids.json"
$statusFile = Join-Path $runtimeData "startup-status.txt"
$apiBase = "http://127.0.0.1:$ApiPort"
$webBase = "http://127.0.0.1:$WebPort"

function Stop-WithMessage([string]$message) {
    "启动失败：$message`r`n日志目录：$logs" | Set-Content -LiteralPath $statusFile -Encoding UTF8
    Write-Host "`n启动失败：$message" -ForegroundColor Red
    Write-Host "日志目录：$logs"
    Write-Host "请查看 START_HERE.md 和免Docker运行操作说明.txt。"
    exit 1
}

function Stop-OwnedProcess([int]$processId) {
    if ($processId -le 0) { return }
    $item = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
    if ($null -ne $item -and $item.ExecutablePath -eq $python) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

if (-not [Environment]::Is64BitOperatingSystem) { Stop-WithMessage "本便携版只支持 64 位 Windows。" }
if (-not (Test-Path -LiteralPath $python)) { Stop-WithMessage "缺少便携运行时 runtime\python.exe。" }
if (-not (Test-Path -LiteralPath (Join-Path $source "alembic.ini"))) { Stop-WithMessage "source 目录不完整。" }

New-Item -ItemType Directory -Force -Path $runtimeData, $logs | Out-Null
"正在启动，请等待首次初始化完成。" | Set-Content -LiteralPath $statusFile -Encoding UTF8

try {
    $existing = Invoke-RestMethod -Uri "$apiBase/ready" -TimeoutSec 3
    if ($existing.status -eq "ready") {
        "系统已经运行。`r`n智能体页面：$webBase`r`nAPI 文档：$apiBase/docs" | Set-Content -LiteralPath $statusFile -Encoding UTF8
        Write-Host "智邻管家已经在运行。" -ForegroundColor Green
        Write-Host "智能体页面：$webBase"
        if (-not $NoBrowser) { Start-Process $webBase }
        exit 0
    }
} catch { }

if (Test-Path -LiteralPath $pidFile) {
    try {
        $old = Get-Content -Raw -Encoding UTF8 $pidFile | ConvertFrom-Json
        foreach ($name in @("web", "worker", "api")) {
            $value = $old.$name
            if ($null -ne $value) { Stop-OwnedProcess ([int]$value) }
        }
    } catch { }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

$pathSeparator = [IO.Path]::PathSeparator
$env:PATH = (Join-Path $root "runtime") + $pathSeparator + $env:PATH
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONNOUSERSITE = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:APP_ENV = "development"
$env:APP_NAME = "智邻管家（北京物业智能体免Docker提交版）"
$dbPath = (Join-Path $runtimeData "zhilin.db").Replace("\", "/")
$env:DATABASE_URL = "sqlite:///$dbPath"
$env:DATA_MODE = "demo"
$env:PRODUCT_MODE = "domestic_beijing"
$env:DEFAULT_DOMESTIC_JURISDICTION = "北京市"
$env:DEMO_COMMUNITY_JURISDICTION = "Demo Garden"
$env:JWT_SECRET = "submission-portable-demo-secret-2026-change-before-production"
$env:DEMO_PASSWORD = "DemoPass123!"
$env:RAG_ENABLED = "true"
$env:RAG_STORAGE_PATH = (Join-Path $runtimeData "knowledge\files")
$env:RAG_CHROMA_PATH = (Join-Path $runtimeData "knowledge\chroma_beijing_v1")
$env:RAG_EMBEDDING_PROVIDER = "hash"
$env:RAG_EMBEDDING_MODEL = "hashing-v1"
$env:RAG_RERANKER_PROVIDER = "lexical"
$env:RAG_RERANKER_MODEL = "lexical-v1"
$env:RAG_LLM_PROVIDER = "disabled"
$env:AGENT_ENABLED = "true"
$env:AGENT_LLM_PROVIDER = "fake"
$env:AGENT_CHECKPOINT_PATH = (Join-Path $runtimeData "agent_checkpoints.sqlite")
$env:STAGE6_READONLY_INTEGRATION_ENABLED = "false"
$env:SUBMISSION_RUNTIME_DIR = $runtimeData
$env:API_BASE_URL = $apiBase

$apiOut = Join-Path $logs "api.out.log"
$apiErr = Join-Path $logs "api.err.log"
$webOut = Join-Path $logs "web.out.log"
$webErr = Join-Path $logs "web.err.log"
$workerOut = Join-Path $logs "worker.out.log"
$workerErr = Join-Path $logs "worker.err.log"

Write-Host "正在初始化运行数据。首次运行会迁移数据库、生成 Demo 数据并重建离线知识索引，通常需要 2—8 分钟..." -ForegroundColor Cyan
$bootstrap = Start-Process -FilePath $python -ArgumentList @(
    "scripts/portable_submission_bootstrap.py"
) -WorkingDirectory $source -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr -WindowStyle Hidden -Wait -PassThru
if ($bootstrap.ExitCode -ne 0) {
    if (Test-Path $apiErr) { Get-Content -Tail 100 -Encoding UTF8 $apiErr }
    if (Test-Path $apiOut) { Get-Content -Tail 100 -Encoding UTF8 $apiOut }
    Stop-WithMessage "首次初始化失败。"
}

Write-Host "正在启动 API..." -ForegroundColor Cyan
$api = Start-Process -FilePath $python -ArgumentList @(
    "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", [string]$ApiPort
) -WorkingDirectory $source -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr -WindowStyle Hidden -PassThru

$deadline = (Get-Date).AddMinutes(10)
$ready = $false
while ((Get-Date) -lt $deadline) {
    if ($api.HasExited) { break }
    try {
        $status = Invoke-RestMethod -Uri "$apiBase/ready" -TimeoutSec 5
        if ($status.status -eq "ready") { $ready = $true; break }
    } catch { Start-Sleep -Seconds 3 }
}
if (-not $ready) {
    Stop-OwnedProcess $api.Id
    if (Test-Path $apiErr) { Get-Content -Tail 80 -Encoding UTF8 $apiErr }
    if (Test-Path $apiOut) { Get-Content -Tail 80 -Encoding UTF8 $apiOut }
    Stop-WithMessage "API 在 10 分钟内未就绪。"
}

Write-Host "正在启动 Web 页面和后台任务..." -ForegroundColor Cyan
$web = Start-Process -FilePath $python -ArgumentList @(
    "-m", "streamlit", "run", "web/app.py", "--server.address", "127.0.0.1",
    "--server.port", [string]$WebPort, "--server.headless", "true"
) -WorkingDirectory $source -RedirectStandardOutput $webOut -RedirectStandardError $webErr -WindowStyle Hidden -PassThru
$worker = Start-Process -FilePath $python -ArgumentList @(
    "-m", "scripts.run_outbox_worker"
) -WorkingDirectory $source -RedirectStandardOutput $workerOut -RedirectStandardError $workerErr -WindowStyle Hidden -PassThru

$webDeadline = (Get-Date).AddMinutes(2)
$webReady = $false
while ((Get-Date) -lt $webDeadline) {
    if ($web.HasExited) { break }
    try {
        $webHealth = Invoke-WebRequest -UseBasicParsing -Uri "$webBase/_stcore/health" -TimeoutSec 5
        if ($webHealth.StatusCode -eq 200) { $webReady = $true; break }
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $webReady) {
    foreach ($processId in @($worker.Id, $web.Id, $api.Id)) { Stop-OwnedProcess $processId }
    if (Test-Path $webErr) { Get-Content -Tail 80 -Encoding UTF8 $webErr }
    Stop-WithMessage "Web 页面在 2 分钟内未就绪。"
}

[ordered]@{
    api = $api.Id
    web = $web.Id
    worker = $worker.Id
    api_port = $ApiPort
    web_port = $WebPort
    python = $python
    started_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -LiteralPath $pidFile -Encoding UTF8

Write-Host "`n启动成功。" -ForegroundColor Green
Write-Host "智能体页面：$webBase"
Write-Host "API 文档：  $apiBase/docs"
Write-Host "演示账户密码统一为：DemoPass123!"
Write-Host "运行日志：$logs"
"启动成功。`r`n智能体页面：$webBase`r`nAPI 文档：$apiBase/docs`r`n演示账户密码：DemoPass123!" | Set-Content -LiteralPath $statusFile -Encoding UTF8
if (-not $NoBrowser) { Start-Process $webBase }
