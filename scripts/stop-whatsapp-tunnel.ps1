$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$taskManifest=Join-Path $taskRoot '.local/rebuild-run/whatsapp-processes.json'
if (-not (Test-Path -LiteralPath $taskManifest)) { Write-Output 'No recorded WhatsApp tunnel.'; return }
$entries=@(Get-Content -LiteralPath $taskManifest -Raw | ConvertFrom-Json)
foreach ($entry in $entries) {
 $process=Get-Process -Id $entry.Id -ErrorAction SilentlyContinue
 if ($process -and $process.StartTime.ToUniversalTime().Ticks -eq $entry.StartTicks) {
  Stop-Process -Id $process.Id
  Write-Output ('Stopped '+$entry.Name)
 }
}
Remove-Item -LiteralPath $taskManifest
