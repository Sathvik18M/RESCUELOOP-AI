param([switch]$Build,[switch]$LocalVerification)
$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
Set-Location -LiteralPath $taskRoot
$taskOverrides=@{LOCAL_VERIFICATION_ONLY='false'}
if ($LocalVerification) {
 $taskOverrides=@{LOCAL_VERIFICATION_ONLY='true';APP_ENV='development';AI_MODE='demo';DEMO_MODE='true';DEMO_TOKEN='local-rescueloop-demo';DATABASE_URL='postgresql+psycopg://rescueloop:rescueloop@127.0.0.1:5432/rescueloop_rebuild';NEXT_PUBLIC_DEMO_MODE='true';NEXT_PUBLIC_API_URL='http://127.0.0.1:8001';NEXT_DIST_DIR='.next-rebuild';CORS_ORIGINS='http://localhost:3100,http://127.0.0.1:3100'}
}
$taskSavedEnvironment=@{}
foreach($entry in $taskOverrides.GetEnumerator()) {
 $taskSavedEnvironment[$entry.Key]=@{Present=(Test-Path -LiteralPath ('Env:\'+$entry.Key));Value=[Environment]::GetEnvironmentVariable($entry.Key,'Process')}
 [Environment]::SetEnvironmentVariable($entry.Key,$entry.Value,'Process')
}
try {
$taskRun = Join-Path $taskRoot '.local/rebuild-run'
[IO.Directory]::CreateDirectory($taskRun) | Out-Null
$taskPython = Join-Path $taskRoot 'services/backend/.venv/Scripts/python.exe'
$taskNode = (Get-Command node -ErrorAction Stop).Source
$taskNext = Join-Path $taskRoot 'node_modules/next/dist/bin/next'
$taskManifest = Join-Path $taskRun 'processes.json'
if (Test-Path -LiteralPath $taskManifest) {
  $existing = Get-Content -LiteralPath $taskManifest -Raw | ConvertFrom-Json
  foreach ($entry in $existing) {
    $process = Get-Process -Id $entry.Id -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().Ticks -eq $entry.StartTicks) { throw 'Rebuild services are already running. Use scripts/stop-local.ps1 first.' }
  }
}
foreach ($port in @(8001,3100)) {
  if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) { throw "Port $port is occupied; leave that service intact and stop it deliberately before starting." }
}
if ($Build -or -not (Test-Path -LiteralPath 'apps/seller-dashboard/.next-rebuild/BUILD_ID')) {
  npm run build
  if ($LASTEXITCODE -ne 0) { throw 'Dashboard build failed.' }
}
$launched = @()
try {
 foreach ($service in @(
   @{Name='api';File=$taskPython;Args=@('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001','--no-access-log');Directory=(Join-Path $taskRoot 'services/backend')},
   @{Name='worker';File=$taskPython;Args=@('-m','app.workers.worker');Directory=(Join-Path $taskRoot 'services/backend')},
   @{Name='dashboard';File=$taskNode;Args=@(('"'+$taskNext+'"'),'start','--hostname','127.0.0.1','--port','3100');Directory=(Join-Path $taskRoot 'apps/seller-dashboard')}
 )) {
   $process = Start-Process -FilePath $service.File -ArgumentList $service.Args -WorkingDirectory $service.Directory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRun ($service.Name+'.out.log')) -RedirectStandardError (Join-Path $taskRun ($service.Name+'.err.log')) -PassThru
   $launched += @{Name=$service.Name;Id=$process.Id;StartTicks=$process.StartTime.ToUniversalTime().Ticks}
   $launched | ConvertTo-Json | Set-Content -LiteralPath $taskManifest
 }
 for ($i=0; $i -lt 20; $i++) {
   try {
     $health=Invoke-RestMethod 'http://127.0.0.1:8001/health' -TimeoutSec 2
     $page=Invoke-WebRequest 'http://127.0.0.1:3100' -TimeoutSec 2
     if ($health.status -eq 'ok' -and $page.StatusCode -eq 200) { Write-Output 'Seller dashboard: http://127.0.0.1:3100'; Write-Output 'API: http://127.0.0.1:8001/docs'; return }
   } catch {}
   Start-Sleep -Seconds 1
 }
 throw 'Services did not become ready. Inspect .local/rebuild-run logs.'
} catch { & (Join-Path $PSScriptRoot 'stop-local.ps1'); throw }
} finally {
 foreach($entry in $taskSavedEnvironment.GetEnumerator()) {
  if ($entry.Value.Present) { [Environment]::SetEnvironmentVariable($entry.Key,$entry.Value.Value,'Process') }
  else { Remove-Item -LiteralPath ('Env:\'+$entry.Key) -ErrorAction SilentlyContinue }
 }
}
