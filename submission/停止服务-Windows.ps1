[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$compose = Join-Path $root "docker\docker-compose.submit.yml"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "未检测到 Docker。"
}
& docker compose -f $compose down
if ($LASTEXITCODE -ne 0) { throw "停止服务失败。" }
Write-Host "服务已停止；演示数据卷保留，下次启动会继续使用。" -ForegroundColor Green
