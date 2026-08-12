[CmdletBinding()]
param(
    [ValidateRange(1, 65535)][int]$ApiPort = 8000,
    [ValidateRange(1, 65535)][int]$WebPort = 8501
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$compose = Join-Path $root "docker\docker-compose.submit.yml"
$apiBase = "http://127.0.0.1:$ApiPort"
$webBase = "http://127.0.0.1:$WebPort"

Write-Host "[1/4] 容器状态" -ForegroundColor Cyan
& docker compose -f $compose ps
if ($LASTEXITCODE -ne 0) { throw "无法读取容器状态。" }

Write-Host "`n[2/4] API 与离线 RAG 就绪检查" -ForegroundColor Cyan
$ready = Invoke-RestMethod -Uri "$apiBase/ready" -TimeoutSec 15
$ready | ConvertTo-Json -Depth 8
if ($ready.status -ne "ready") { throw "API 未就绪。" }

Write-Host "`n[3/4] 登录与产品上下文检查" -ForegroundColor Cyan
$loginBody = @{ username = "resident_demo"; password = "DemoPass123!" } | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri "$apiBase/api/v1/auth/login" -ContentType "application/json" -Body $loginBody -TimeoutSec 15
$headers = @{ Authorization = "Bearer $($login.data.access_token)" }
$context = Invoke-RestMethod -Uri "$apiBase/api/v1/product-context" -Headers $headers -TimeoutSec 15
[pscustomobject]@{
    default_mode = $context.data.default_mode
    supported_modes = $context.data.supported_modes
    real_property_authorization = $context.data.real_property_authorization
} | ConvertTo-Json -Depth 4
if ($context.data.default_mode -ne "domestic_beijing") { throw "默认模式不是 domestic_beijing。" }
if ($context.data.real_property_authorization -ne $false) { throw "真实物业授权标识不符合提交版边界。" }

Write-Host "`n[4/4] Web 健康检查" -ForegroundColor Cyan
$web = Invoke-WebRequest -UseBasicParsing -Uri "$webBase/_stcore/health" -TimeoutSec 15
if ($web.StatusCode -ne 200) { throw "Web 健康检查失败。" }

Write-Host "`nPASS：容器、API、离线 RAG、默认北京模式、数据边界和 Web 均正常。" -ForegroundColor Green
