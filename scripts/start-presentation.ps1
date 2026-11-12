param([int]$Port = 3100)
$ErrorActionPreference = 'Stop'
$presentationRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$presentationNode = (Get-Command node -ErrorAction Stop).Source
$presentationNext = Join-Path $presentationRoot 'node_modules/next/dist/bin/next'
if (-not (Test-Path -LiteralPath $presentationNext)) {
  throw 'Install dependencies first: npm ci'
}
$presentationOverrides = @{
  NEXT_PUBLIC_DEMO_MODE = 'false'
  NEXT_PUBLIC_API_URL = '/backend'
  NEXT_DIST_DIR = '.next-presentation'
  LOCAL_API_PROXY = 'true'
}
$presentationSaved = @{}
foreach ($entry in $presentationOverrides.GetEnumerator()) {
  $presentationSaved[$entry.Key] = [Environment]::GetEnvironmentVariable($entry.Key, 'Process')
  [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
}
Push-Location -LiteralPath (Join-Path $presentationRoot 'apps/seller-dashboard')
try {
  Write-Output "Open http://127.0.0.1:$Port and sign in with your seller account."
  Write-Output 'Uses the existing hosted backend and saved conversations. Internet is required.'
  Write-Output 'Keep this window open. Press Ctrl+C to stop the local dashboard.'
  & $presentationNode $presentationNext dev --webpack --hostname 127.0.0.1 --port $Port
} finally {
  Pop-Location
  foreach ($entry in $presentationSaved.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
  }
}
