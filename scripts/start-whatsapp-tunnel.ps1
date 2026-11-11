$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
Set-Location -LiteralPath $taskRoot
$taskRun=Join-Path $taskRoot '.local/rebuild-run'
$taskManifest=Join-Path $taskRun 'whatsapp-processes.json'
$taskCloudflared=Join-Path $taskRoot '.local/bin/cloudflared.exe'
$taskPython=Join-Path $taskRoot 'services/backend/.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskCloudflared)) { throw 'Install the official cloudflared Windows binary at .local/bin/cloudflared.exe first.' }
if (Test-Path -LiteralPath $taskManifest) { throw 'Stop the recorded WhatsApp tunnel before starting another.' }
if (Get-NetTCPConnection -State Listen -LocalPort 8003 -ErrorAction SilentlyContinue) { throw 'Port 8003 is occupied.' }
[IO.Directory]::CreateDirectory($taskRun) | Out-Null
$taskEntries=@()
try {
 $tunnel=Start-Process -FilePath $taskCloudflared -ArgumentList @('tunnel','--url','http://127.0.0.1:8003','--no-autoupdate','--protocol','http2') -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRun 'tunnel.out.log') -RedirectStandardError (Join-Path $taskRun 'tunnel.err.log') -PassThru
 $taskEntries+=@{Name='WhatsApp tunnel';Id=$tunnel.Id;StartTicks=$tunnel.StartTime.ToUniversalTime().Ticks}
 $taskEntries | ConvertTo-Json | Set-Content -LiteralPath $taskManifest
 $origin=$null
 for($i=0;$i -lt 45;$i++) {
  $taskLog=Get-Content -LiteralPath (Join-Path $taskRun 'tunnel.err.log') -Raw -ErrorAction SilentlyContinue
  if ($taskLog -match 'https://[a-z0-9-]+\.trycloudflare\.com') {$origin=$Matches[0];break}
  if ($tunnel.HasExited) {throw 'Tunnel stopped before allocating an HTTPS origin.'}
  Start-Sleep -Seconds 1
 }
 if (-not $origin) {throw 'No public origin was allocated. Inspect the tunnel log.'}
 & $taskPython (Join-Path $PSScriptRoot 'configure_webhook.py') $origin
 if ($LASTEXITCODE -ne 0) {throw 'Webhook configuration failed.'}
 $gateway=Start-Process -FilePath $taskPython -ArgumentList @('-m','uvicorn','app.webhook_gateway:app','--host','127.0.0.1','--port','8003','--no-access-log') -WorkingDirectory (Join-Path $taskRoot 'services/backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRun 'gateway.out.log') -RedirectStandardError (Join-Path $taskRun 'gateway.err.log') -PassThru
 $taskEntries+=@{Name='WhatsApp gateway';Id=$gateway.Id;StartTicks=$gateway.StartTime.ToUniversalTime().Ticks}
 $taskEntries | ConvertTo-Json | Set-Content -LiteralPath $taskManifest
 Write-Output ('WhatsApp webhook origin: '+$origin)
 Write-Output 'For 360dialog, run scripts/configure_360dialog.py to register the private callback URL without printing its secret.'
 Write-Output 'Restart the main API and worker to load the new origin. Seller routes are excluded from this gateway.'
} catch { & (Join-Path $PSScriptRoot 'stop-whatsapp-tunnel.ps1'); throw }
