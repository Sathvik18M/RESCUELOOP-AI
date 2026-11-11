$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
npm ci
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' }
Push-Location -LiteralPath 'services/backend'
try {
    uv sync --python 3.12 --frozen
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed' }
} finally { Pop-Location }
docker compose -f infra/compose.yaml up -d --wait
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed' }
& '.\services\backend\.venv\Scripts\python.exe' 'scripts/local-database.py'
if ($LASTEXITCODE -ne 0) { throw 'Isolated database creation failed' }
Push-Location -LiteralPath 'services/backend'
try {
    .\.venv\Scripts\python.exe -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed' }
    .\.venv\Scripts\python.exe -m app.cli seed
    if ($LASTEXITCODE -ne 0) { throw 'Demo seeding failed' }
} finally { Pop-Location }
Write-Output 'Setup complete. Start the API, worker, and dashboard using the README commands.'
