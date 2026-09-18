$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
$Local = Join-Path $Root "local"
$Nginx = "C:\ServBay\packages\nginx\nginx.exe"
$Prefix = ($Local + "\").Replace("\", "/")
$conf = "$Prefix/nginx.conf"

if (Test-Path (Join-Path $Local "nginx.pid")) {
  & $Nginx -s quit -p $Prefix -c $conf 2>$null
  Start-Sleep -Seconds 1
}
Get-NetTCPConnection -LocalPort 18080,18081,18082 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Push-Location $Root
docker compose -f compose/docker-compose.yml -f local/docker-compose.override.yml down
Pop-Location
Write-Host "已停本机演示。ServBay 80/443 未动。"
