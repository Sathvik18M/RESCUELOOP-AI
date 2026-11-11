# RescueLoop AI

A WhatsApp commerce and support platform with a Next.js seller dashboard, a FastAPI backend, policy-controlled AI workflows, and PostgreSQL persistence.

This first implementation runs the four approved demo journeys against real database records. Customer messages can be entered through the dashboard's **demo inbox** without external credentials. Payment and courier operations are explicitly simulated.

## Run locally on Windows

Prerequisites: Node.js 24, Python 3.12 through `uv`, and Docker Desktop with its Linux engine running.

```powershell
cd D:\Projects\RESCUELOOP-AI
.\scripts\setup.ps1
```

The setup script installs locked dependencies, copies `.env.example` to `.env` if needed, starts PostgreSQL, applies migrations, and inserts the two synthetic demo orders. Repeated seeding preserves existing records.

Start the API in one terminal:

```powershell
cd D:\Projects\RESCUELOOP-AI\services\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Start the background worker in another:

```powershell
cd D:\Projects\RESCUELOOP-AI\services\backend
.\.venv\Scripts\python.exe -m app.jobs.worker
```

Start the dashboard:

```powershell
cd D:\Projects\RESCUELOOP-AI
npm run dev
```

- Dashboard: <http://127.0.0.1:3000>
- API documentation: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/health>
- Default local demo token: `local-rescueloop-demo` (matches `.env.example`).

The demo token is deliberately a local development credential. The application refuses to enable demo authentication in `APP_ENV=production`.

On macOS/Linux, use `uv sync --python 3.12 --frozen` in `services/backend`, activate `.venv/bin/activate`, and use `python` for the same API, migration, seed, and worker commands. The npm and Docker commands are unchanged.

## Included

- Seller overview, inbox with human takeover, orders, approval center, inventory editing, policy studio, pickups, returns/refunds, evidence, reviews, insights, action log, and settings.
- Two seeded orders: `ORD1042` (headphones/failed delivery) and `ORD1043` (wallet/customization draft).
- Seller quotations followed by explicit customer confirmation.
- Stock and pickup capacity reservation, private collection-code verification, and simulated collection payment.
- Redelivery requests, cancellations, returns, replacements, warranty requests, and cumulative refund limits.
- Versioned published policies. Publishing a new version expires pending requests to prevent stale approval execution.
- Private evidence uploads, image normalization, and authenticated viewing.
- LangGraph routing with PostgreSQL checkpoints; domain case records persist seller/customer approval waits.
- OpenAI Responses integrations for conversation routing, shopping, resolution, policy drafting, image assessment, and feedback analysis. `AI_MODE=demo` uses deterministic scenarios and labels visual analysis as not run.
- Signed WhatsApp webhooks, persistent incoming/outgoing jobs, bounded retry, delivery receipts, and request expiration jobs.
- Supabase JWT authentication and store membership checks, private object storage adapter, PostgreSQL RLS migrations, and deployment configuration.

## Repository layout

```text
apps/seller-dashboard/src/    Next.js routes, components, feature screens, API/auth clients
services/backend/app/api/    HTTP endpoints and WhatsApp webhooks
services/backend/app/core/   Configuration and authorization
services/backend/app/db/     SQLAlchemy models and database sessions
services/backend/app/modules/ Business workflows and transaction rules
services/backend/app/agents/ AI specialists and versioned prompts
services/backend/app/workflows/ LangGraph routing
services/backend/app/integrations/ WhatsApp and private storage
services/backend/app/jobs/   Persistent job worker
services/backend/migrations/ Versioned Alembic schema migrations
services/backend/tests/      Isolated backend workflow tests
contracts/                  Generated OpenAPI schema
data/demo/                  Synthetic seeds, scenario description, test image
tests/e2e/                  Playwright customer/seller journey tests
scripts/                    Setup, contract export, isolated browser-test server
infra/                      PostgreSQL Compose, backend image, Render blueprint
docs/                       Architecture, demonstration, deployment, and release scope
```

Runtime files, uploads, logs, and screenshots belong in ignored `.local/`; secrets belong in ignored `.env` or deployment secret settings. Source code, migrations, seeds, prompts, and lockfiles are versioned.

## Verify

```powershell
npm run build
npm run typecheck
cd services/backend
.\.venv\Scripts\python.exe -m pytest -q
```

To verify PostgreSQL transaction behavior, first create a dedicated database:

```powershell
docker compose -f infra/compose.yaml exec -T postgres createdb -U rescueloop rescueloop_test
cd services/backend
$env:TEST_DATABASE_URL = 'postgresql+psycopg://rescueloop:rescueloop@127.0.0.1:5432/rescueloop_test'
.\.venv\Scripts\python.exe -m pytest -q
```

Browser verification from the repository root:

```powershell
npm run test:e2e
```

Playwright uses Microsoft Edge on Windows and Chromium in CI. It starts separate servers on ports 3001/8001 and resets **only** the dedicated `rescueloop_e2e` database. The normal demo store is untouched. CI includes PostgreSQL tests, a production frontend build, contract checking, and browser journeys.

Regenerate the API contract after changing endpoints:

```powershell
.\services\backend\.venv\Scripts\python.exe scripts/export_contracts.py
npm run contracts
```

Webpack is used for Next.js development/build because Turbopack's compiler subprocess failed on the development Windows host. Dependencies are pinned through `package-lock.json` and `services/backend/uv.lock`.

## Next steps

Read [the demo script](docs/demo.md), [architecture](docs/architecture.md), [release scope](docs/release-scope.md), and [live-service setup](docs/deployment.md). Live OpenAI, Meta, and Supabase calls require your own configured credentials; those external services have not been exercised by the local demo tests.
