# 本机 ServBay 演示：Docker 三容器 + ServBay nginx.exe 独立前缀（18080/18081/18082）
# 不改 ServBay 的 80/443，不碰真机。
$ErrorActionPreference = "Stop"
$Local = $PSScriptRoot
$Root = Split-Path -Parent $Local
$Nginx = "C:\ServBay\packages\nginx\nginx.exe"
$Prefix = ($Local + "\").Replace("\", "/")

New-Item -ItemType Directory -Force -Path (Join-Path $Local "logs"), (Join-Path $Local "temp\client_body_temp"), (Join-Path $Local "temp\proxy_temp") | Out-Null

Write-Host "=== docker compose up --build ==="
Push-Location $Root
try {
  docker compose -f compose/docker-compose.yml -f local/docker-compose.override.yml up -d --build
  if ($LASTEXITCODE -ne 0) { throw "docker compose failed" }
} finally {
  Pop-Location
}

Write-Host "=== wait backend /health ==="
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:5200/health" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) { $ready = $true; break }
  } catch { }
  Start-Sleep -Seconds 2
}
if (-not $ready) { throw "backend /health 未在 120s 内就绪，看: docker logs looma-backend" }

$dist = Join-Path $Root "frontend\packages\saas\dist\index.html"
if (Test-Path $dist) {
  Write-Host "=== sync tspace dist → local/www/tspace ==="
  $dest = Join-Path $Local "www\tspace"
  if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
  Copy-Item -Recurse (Join-Path $Root "frontend\packages\saas\dist") $dest
} else {
  Write-Host "=== 无 frontend/packages/saas/dist，18082 沿用已有 local/www/tspace（先跑 bash scripts/build-saas.sh）==="
}

Write-Host "=== servbay nginx.exe -t / start (prefix local/) ==="
$conf = "$Prefix/nginx.conf"
$t = & $Nginx -t -p $Prefix -c $conf 2>&1
if ($LASTEXITCODE -ne 0) { $t | Write-Host; throw "nginx -t failed" }

$pidFile = Join-Path $Local "nginx.pid"
if (Test-Path $pidFile) {
  & $Nginx -s quit -p $Prefix -c $conf 2>$null
  Start-Sleep -Seconds 1
}
Start-Process -FilePath $Nginx -ArgumentList @("-p", $Prefix, "-c", $conf) -WindowStyle Hidden

Write-Host ""
Write-Host "打开:"
Write-Host "  官网   http://127.0.0.1:18080/          (/pricing /legal/privacy|terms|refund)"
Write-Host "  API    http://127.0.0.1:18081/health"
Write-Host "  tspace http://127.0.0.1:18082/"
Write-Host "  说明   http://127.0.0.1:18080/hub.html"
Write-Host "ServBay :80/:443 未改。"
