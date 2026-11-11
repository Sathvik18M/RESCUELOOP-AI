$ErrorActionPreference = 'Stop'
$taskRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$taskManifest = Join-Path $taskRoot '.local/rebuild-run/processes.json'
if (-not (Test-Path -LiteralPath $taskManifest)) { Write-Output 'No recorded rebuild processes.'; exit 0 }
$entries = @(Get-Content -LiteralPath $taskManifest -Raw | ConvertFrom-Json)
$taskProcesses = @(Get-CimInstance Win32_Process)
function Stop-OwnedTree([int]$ProcessId) {
 foreach ($child in $taskProcesses | Where-Object ParentProcessId -eq $ProcessId) { Stop-OwnedTree $child.ProcessId }
 Stop-Process -Id $ProcessId -ErrorAction SilentlyContinue
}
foreach ($entry in $entries) {
 $process = Get-Process -Id $entry.Id -ErrorAction SilentlyContinue
 if ($process -and $process.StartTime.ToUniversalTime().Ticks -eq $entry.StartTicks) {
   Stop-OwnedTree $process.Id
   Write-Output ("Stopped rebuild "+$entry.Name)
 }
}
Remove-Item -LiteralPath $taskManifest
