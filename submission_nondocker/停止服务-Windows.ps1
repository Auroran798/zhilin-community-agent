[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root "runtime\python.exe"
$pidFile = Join-Path $root "runtime_data\service-pids.json"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "未发现本提交包的运行进程记录；服务可能已经停止。" -ForegroundColor Yellow
    exit 0
}

$state = Get-Content -Raw -Encoding UTF8 $pidFile | ConvertFrom-Json
foreach ($name in @("web", "worker", "api")) {
    $processId = [int]$state.$name
    if ($processId -le 0) { continue }
    $item = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
    if ($null -ne $item -and $item.ExecutablePath -eq $python) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        Write-Host "已停止 $name（PID $processId）。"
    }
}
Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
Write-Host "服务已停止；runtime_data 中的演示数据已保留。" -ForegroundColor Green
