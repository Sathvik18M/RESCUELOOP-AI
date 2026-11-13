# RescueLoop AI
#Rescueloop AI 
RescueLoop is a seller-only support portal with a WhatsApp customer interface. The rebuild implements the [16 approved decisions](docs/decisions/approved-baseline.md) using Next.js / TypeScript / Tailwind, FastAPI, LangGraph / Groq, PostgreSQL / SQLAlchemy / Alembic, Supabase Auth / private Storage, a provider-independent WhatsApp adapter (360dialog Sandbox or Twilio), and a persistent Python worker.

The five seller sections are **Overview, Inbox, Requests, Policies, Insights**. Case drawers hold order context, evidence, proposals, seller decisions, conversation history and audit activity. Customers never enter messages through the seller website. Payments, courier actions and collection payments are explicitly simulated.

The [35 customer issue response paths](docs/support-issues.md) cover order, delivery, product, refund, billing, customization, warranty and human-support requests. Complaints do not imply permission to perform an action. Missing details and seller review stay open; technical failures send an explicit service notice instead of silently dropping the message.

The previous prototype is preserved at commit `4f399b8`. The rebuild uses the separate `rescueloop_rebuild` database locally. The original `rescueloop` database is untouched. See [the free hosted demo setup](docs/deployment.md#free-hosted-demo) for deployment requirements and limitations.

Hosted seller demo: [rescueloop-ai-xi.vercel.app](https://rescueloop-ai-xi.vercel.app). It requires the existing seller's Supabase sign-in. The free Render backend uses the migrated Supabase database. Real customer-initiated WhatsApp text and a Groq-generated reply with delivered/read receipts were verified on 12 November 2026. Sandbox quotas and free-host cold starts still apply.

## Local setup and launch

For a presentation using the existing hosted database and seller account, run:

```powershell
cd D:\Projects\RESCUELOOP-AI
.\scripts\start-presentation.ps1
```

Open http://127.0.0.1:3100 and sign in. Keep the terminal open; Ctrl+C stops it.
This runs only the dashboard locally and proxies seller API requests to the existing
Render backend, avoiding cross-origin failures. Internet is required. It shows the
same saved conversations as the deployed site and does not start another backend,
worker, or WhatsApp webhook. The existing `.env` is left unchanged.

For the separate local database and deterministic verification setup:

Prerequisites: Node.js 24, Python 3.12 / uv, PowerShell 7 and Docker Desktop.

```powershell
cd D:\Projects\RESCUELOOP-AI
.\scripts\setup.ps1
.\scripts\start-local.ps1 -Build -LocalVerification
```

Setup installs locked dependencies, creates `.env` only if absent, starts Docker PostgreSQL, creates the isolated database, migrates and seeds it. Do not point setup at an existing production database. Repeated seeding leaves saved records unchanged.

- [Seller dashboard](http://127.0.0.1:3100)
- [API documentation](http://127.0.0.1:8001/docs)
- [Health](http://127.0.0.1:8001/health)
- Local verification token: `local-rescueloop-demo`.

`-LocalVerification` isolates the running processes from provider credentials being entered in `.env`. It uses deterministic routing and private local images. It does not modify `.env`. Omit that switch when deliberately testing configured integrations. Use `-Build` after changing browser environment settings.

```powershell
.\scripts\stop-local.ps1
```

Start/stop records owned process IDs and creation timestamps under `.local/rebuild-run/`; the old prototype services are not stopped. Logs are in the same directory.

Manual development: run `python -m uvicorn app.main:app --host 127.0.0.1 --port 8001` and `python -m app.workers.worker` from `services/backend`, plus `npm run dev -- --port 3100` from the repository root. Use the virtual environment’s Python.

## Configuration

The root [`.env.example`](.env.example) is the complete template. Use one `KEY=value` per line; never commit populated secrets. Groq uses `openai/gpt-oss-20b` for text and `qwen/qwen3.8-27b` for vision. Both run on Groq; the latter is a preview model. Setting keys is separate from verifying live connections.

Messaging defaults to disabled. Select `WHATSAPP_PROVIDER=360dialog_sandbox` for the optional text-only Sandbox, or explicitly select `twilio` to use the retained Twilio integration. There is no automatic fallback. Follow [provider setup and live acceptance](docs/deployment.md#360dialog-sandbox-optional-provider). A configured provider is not proof of real WhatsApp delivery.

Use `APP_ENV`, not `ENVIRONMENT`. Keep the local `DATABASE_URL` while developing. `SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_URL` identify the same project. The server uses the Supabase `service_role` key; the browser uses the `anon` key. Never place a privileged secret in a `NEXT_PUBLIC_` variable. `SELLER_USER_ID` is an existing Supabase Auth user UUID.

See [integration setup](docs/deployment.md) for seller provisioning, the private bucket, Sandbox joining, phone ownership and webhook configuration.

## Demo

Initial seed: Loop & Co., three customers/orders/products, twelve cases across fourteen days: **6 resolved, 4 ongoing, 2 flagged**. Headphones ₹1,999; wallet ₹799; cable ₹199. Refund cap ₹250, seven-day returns, engraving ₹199, wrap ₹149, one-day preparation, 24-hour proposals, two dated five-capacity pickup windows. Prices include tax; additional delivery/tax charges are outside this fixed demo.

Use [the walkthrough](docs/demo.md) for customization, pickup, inspection/refund, private photo review, handoff and insights. Local customer input is an authenticated CLI fixture:

```powershell
.\scripts\demo-message.ps1 -Conversation CONV002 -Text 'Can I collect the wallet tomorrow afternoon?'
```

Actual customers use WhatsApp after live setup. The fixture refuses WhatsApp conversations and is disabled when `DEMO_MODE=false`.

## Repository responsibilities

```text
apps/seller-dashboard/src/
  app/                   Next.js entry points and styles
  features/              Five sections and shared case detail
  components/            Reusable visual primitives
  lib/                   API, authentication, shared types
services/backend/app/
  api/                   Scoped HTTP endpoints and authenticated provider webhooks
  domain/                Policies, cases, consent, inventory, refunds, metrics
  agents/                Groq client, routing, specialists and LangGraph workflow
  integrations/          Messaging adapter, provider transports and private evidence storage
  persistence/           SQLAlchemy records and sessions
  workers/               Durable jobs, pacing, retry and recovery
  core/                  Settings and store authorization
services/backend/migrations/  Alembic changes; head 0007
services/backend/tests/       Workflow and integration-boundary tests
packages/contracts/          Generated OpenAPI and TypeScript contracts
data/demo/                   Synthetic catalog, scenarios and test image
scripts/                     Setup, run/stop, fixtures, concurrency verification
infra/                       Local PostgreSQL and deployment templates
docs/decisions/              Approved specification
docs/screenshots/            Reviewed synthetic-demo screenshots
```

Runtime data, local uploads, logs, caches and databases are excluded from Git. Do not edit generated contracts manually.

## Verification

```powershell
npm run typecheck
npm run build
services/backend/.venv/Scripts/python.exe scripts/export_contracts.py
npm run contracts
cd services/backend
.venv/Scripts/python.exe -m pytest tests -vv
```

To run PostgreSQL checks, create a dedicated `rescueloop_test_rebuild` database and apply migrations to it, then set `TEST_DATABASE_URL` to that database before pytest. Test guards reject non-test names; tests never reset the demo database. The additional `scripts/verify_concurrency.py` exercises competing pickup and refund transactions in that dedicated database and removes its own fixtures.

The Playwright suite is available through `npm run test:e2e` and CI. It uses a separate `rescueloop_e2e` database, API 8002 and dashboard 3001. See [validation status](docs/validation.md) for checks actually run versus pending live checks.

## Explicit demo reset

Stop the API and worker, wait at least 30 seconds for the heartbeat to expire, then run:

```powershell
cd services/backend
.venv/Scripts/python.exe -m app.cli reset --store SELLER001 --confirm-store SELLER001
.venv/Scripts/python.exe -m app.cli seed
```

Reset requires development demo mode and synthetic seed provenance. It removes that store’s records, queued jobs, private evidence (including orphaned uploads) and conversation checkpoints. Other stores remain intact. Reset refuses active worker heartbeats/leases. Storage deletion must succeed before database references are removed. The audit records the explicit reset. Use only the intended isolated demo database.

Sachin S Kumar i am doing the developer 
