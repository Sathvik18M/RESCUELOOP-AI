# Live-service setup and deployment

## Configuration

Copy `.env.example` to `.env` for local configuration. The dashboard's Next.js config loads the root environment file. Only `NEXT_PUBLIC_*` values are compiled into the client. Keep all service-role, OpenAI, WhatsApp, and database credentials server-side.

For live AI in the local demo, set `AI_MODE=openai`, `OPENAI_API_KEY`, and a model ID available to your account with Responses function calling, structured outputs, and image inputs. Restart the API and worker. The model ID in the example is a configurable starting point; account access and model availability must be checked during connection.

## Supabase

1. Create a project and configure an asymmetric signing key for Auth JWTs. This implementation validates RS256/ES256 against the project's JWKS endpoint.
2. Set `DATABASE_URL` using `postgresql+psycopg://...`. Use a session/direct connection appropriate for SQLAlchemy and LangGraph checkpoints; do not point checkpoint writes at a transaction pooler that breaks session requirements.
3. Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET=evidence`.
4. Create a **private** `evidence` storage bucket. Keep browser access policies closed; the server mediates file access.
5. Apply `python -m alembic upgrade head` from the backend directory. Application tables enable RLS and expose no direct browser data policies.
6. In a fresh production database, create an Auth user, then run `python -m app.cli init-store --user-id <supabase-user-uuid> --name "Your Store"`. The command maps the store to the configured WhatsApp phone ID. Import real catalog/orders separately; never import the synthetic customer phone numbers as real customer identities.
7. Set the frontend's `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_DEMO_MODE=false`.

## WhatsApp

Configure the Meta business app and Cloud API phone number. Set access token, phone-number ID, app secret, verify token, and an explicitly supported Graph API version. The example version is configuration, not a promise that the account supports it.

Subscribe the HTTPS endpoint `/webhooks/whatsapp` to messages. Verify that Meta's challenge succeeds and invalid signatures fail. Test text, image delivery, and outgoing status updates with an authorized test customer number. Existing orders must be mapped to that customer's WhatsApp phone number before order-specific actions are permitted.

Set `WHATSAPP_UPDATE_TEMPLATE` to an approved template with **one text body parameter** and English language code `en`, matching the adapter. Change the template configuration/code together if your approved template uses another language or structure. Worker deliveries outside the customer-service window require this template. The deployment must also observe the account's current opt-in and messaging requirements.

## Host the API and worker on Render

Use `infra/render.yaml` as the Blueprint and `infra/Dockerfile.backend` as the build configuration. Set secret values separately for the API and worker. Apply migrations through a deployment/pre-deploy task before serving traffic. Provision the store membership before signing in.

Production requires `APP_ENV=production`, `DEMO_MODE=false`, `AI_MODE=openai`, PostgreSQL, and configured OpenAI, Supabase, and WhatsApp credentials. Startup fails when those requirements are not met. Payment/courier adapters remain simulated regardless of this flag until a real provider integration is implemented.

## Host the dashboard on Vercel

Import the repository, choose Next.js, and set the project root to `apps/seller-dashboard`. Enable access to files outside the root for the npm workspace. Install from the root lockfile and build the dashboard workspace. Configure:

- `NEXT_PUBLIC_API_URL`: deployed HTTPS API origin.
- `NEXT_PUBLIC_DEMO_MODE=false`.
- `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`.

Set backend `CORS_ORIGINS` to the exact dashboard HTTPS origin(s), separated by commas. Rebuild the dashboard whenever public environment values change.

## Operational checks

Verify sign-in, cross-store denial, private evidence access, signed webhook ingestion, customer order ownership, template delivery, the four demo-derived journeys against staging data, and worker restart recovery. Inspect `jobs` for `failed`/`needs_review`. A send with an uncertain outcome must be checked against Meta before a human retries it.

Back up PostgreSQL and object storage separately. Application table data, agent checkpoint data, and image objects all contain operational/customer information and need an appropriate retention policy.

No cloud service was provisioned or published as part of the local implementation.
