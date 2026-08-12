[CmdletBinding()]
param(
    [ValidateRange(1, 65535)][int]$ApiPort = 8000,
    [ValidateRange(1, 65535)][int]$WebPort = 8501,
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$compose = Join-Path $root "docker\docker-compose.submit.yml"
$imageTar = Join-Path $root "docker\zhilin-beijing-amd64.tar"
$image = "zhilin-beijing:2026.08.11-amd64"
$env:API_PORT = [string]$ApiPort
$env:WEB_PORT = [string]$WebPort
$apiBase = "http://127.0.0.1:$ApiPort"
$webBase = "http://127.0.0.1:$WebPort"

function Stop-WithMessage([string]$message) {
    Write-Host "`n启动失败：$message" -ForegroundColor Red
    Write-Host "请查看 START_HERE.md 的故障排查章节。"
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Stop-WithMessage "未检测到 Docker。请先安装并启动 Docker Desktop。"
}
if (-not (Test-Path -LiteralPath $compose)) { Stop-WithMessage "缺少 $compose" }
if (-not (Test-Path -LiteralPath $imageTar)) { Stop-WithMessage "缺少离线镜像 $imageTar" }

& docker info *> $null
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "Docker 引擎未运行，请先打开 Docker Desktop，等待其显示 Running。" }

& docker image inspect $image *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "正在导入离线镜像（文件较大，通常需要 1—5 分钟）..." -ForegroundColor Cyan
    & docker load --input $imageTar
    if ($LASTEXITCODE -ne 0) { Stop-WithMessage "离线镜像导入失败。" }
} else {
    Write-Host "已检测到本地镜像，跳过重复导入。" -ForegroundColor DarkGray
}

Write-Host "正在启动智邻管家。首次启动会创建演示数据库并导入受控知识库，可能需要数分钟..." -ForegroundColor Cyan
& docker compose -f $compose up -d --remove-orphans
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "docker compose 启动失败。" }

$deadline = (Get-Date).AddMinutes(10)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $status = Invoke-RestMethod -Uri "$apiBase/ready" -TimeoutSec 5
        if ($status.status -eq "ready") { $ready = $true; break }
    } catch { Start-Sleep -Seconds 3 }
}

if (-not $ready) {
    & docker compose -f $compose ps
    & docker compose -f $compose logs --tail 120 api
    Stop-WithMessage "API 在 10 分钟内未就绪。"
}

$webDeadline = (Get-Date).AddMinutes(2)
$webReady = $false
while ((Get-Date) -lt $webDeadline) {
    try {
        $webHealth = Invoke-WebRequest -UseBasicParsing -Uri "$webBase/_stcore/health" -TimeoutSec 5
        if ($webHealth.StatusCode -eq 200) { $webReady = $true; break }
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $webReady) {
    & docker compose -f $compose logs --tail 80 web
    Stop-WithMessage "Web 页面未就绪。"
}

Write-Host "`n启动成功。" -ForegroundColor Green
Write-Host "智能体页面：$webBase"
Write-Host "API 文档：  $apiBase/docs"
Write-Host "演示账户密码统一为：DemoPass123!"
if (-not $NoBrowser) { Start-Process $webBase }
