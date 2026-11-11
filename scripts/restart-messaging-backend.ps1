# Restart only the recorded API, worker and webhook gateway. Preserve dashboard and tunnel.
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$taskRun=Join-Path $taskRoot '.local/rebuild-run'
$taskPython=Join-Path $taskRoot 'services/backend/.venv/Scripts/python.exe'
$taskBackend=Join-Path $taskRoot 'services/backend'
foreach($group in @(
 @{Manifest='processes.json';Services=@(
   @{Name='api';Args=@('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8001','--no-access-log');Log='api'},
   @{Name='worker';Args=@('-m','app.workers.worker');Log='worker'})},
 @{Manifest='whatsapp-processes.json';Services=@(
   @{Name='WhatsApp gateway';Args=@('-m','uvicorn','app.webhook_gateway:app','--host','127.0.0.1','--port','8003','--no-access-log');Log='gateway'})}
)) {
 $taskManifest=Join-Path $taskRun $group.Manifest
 $taskEntries=@(Get-Content -LiteralPath $taskManifest -Raw | ConvertFrom-Json)
 foreach($service in $group.Services) {
  $entry=@($taskEntries | Where-Object Name -eq $service.Name)
  if($entry.Count -ne 1) {throw ('Missing unique recorded service: '+$service.Name)}
  $process=Get-Process -Id $entry[0].Id -ErrorAction SilentlyContinue
  if($process) {
   if($process.StartTime.ToUniversalTime().Ticks -ne $entry[0].StartTicks) {throw 'Recorded process identity changed; refusing to stop it.'}
   Stop-Process -Id $process.Id
   Wait-Process -Id $process.Id -ErrorAction SilentlyContinue
  }
  $launched=Start-Process -FilePath $taskPython -ArgumentList $service.Args -WorkingDirectory $taskBackend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRun ($service.Log+'.out.log')) -RedirectStandardError (Join-Path $taskRun ($service.Log+'.err.log')) -PassThru
  $entry[0].Id=$launched.Id
  $entry[0].StartTicks=$launched.StartTime.ToUniversalTime().Ticks
  $taskEntries | ConvertTo-Json | Set-Content -LiteralPath $taskManifest
 }
}
for($i=0;$i -lt 20;$i++) {
 try {
  $api=Invoke-RestMethod 'http://127.0.0.1:8001/health' -TimeoutSec 2
  $gateway=Invoke-RestMethod 'http://127.0.0.1:8003/health' -TimeoutSec 2
  if($api.status -eq 'ok' -and $gateway.status -eq 'ok') {Write-Output 'Messaging backend restarted; dashboard and tunnel preserved.';return}
 } catch {}
 Start-Sleep -Seconds 1
}
throw 'Backend health check failed; inspect private local logs.'
