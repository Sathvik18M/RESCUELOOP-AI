# Integration setup and readiness

The local app uses a temporary Cloudflare tunnel for signed WhatsApp callbacks. No production deployment has been created. Actual WhatsApp acceptance requires an observed incoming message and delivered reply.

## Environment

Start from the root `.env.example`. `APP_ENV=development` is the recognized environment key. The selected provider is Groq: `GROQ_API_KEY`, `GROQ_MODEL=openai/gpt-oss-20b`, and `GROQ_VISION_MODEL=qwen/qwen3.8-27b`. Text uses strict JSON schema output; vision uses JSON mode plus local Pydantic validation. Qwen is currently a preview model. See [Groq models](https://console.groq.com/docs/models) and [vision documentation](https://console.groq.com/docs/vision). The `openai/` prefix identifies an open-weight model hosted on Groq; no OpenAI API key or billing is used.

Set `AI_MODE=groq` only with a usable key. Keep `DATABASE_URL` pointed at the isolated local PostgreSQL database unless deliberately migrating to a hosted database. The Supabase URL is not a PostgreSQL connection string.

```powershell
cd services/backend
.venv/Scripts/python.exe -m app.cli readiness
```

Readiness prints presence/status flags only, never secret values. It does not prove live delivery or model behavior.

## Supabase

Create the private `evidence` bucket. Configure the server URL and legacy `service_role` key, plus the same URL and `anon` key for browser authentication. Keep privileged credentials server-side. Private object access uses expiring signed URLs: [Supabase private assets](https://supabase.com/docs/guides/storage/serving/downloads).

Create the seller Auth user through your Supabase project. Provision that existing user UUID explicitly:

```powershell
.venv/Scripts/python.exe -m app.cli provision-owner --store SELLER001 --user-id YOUR_AUTH_USER_UUID
```

`SELLER_USER_ID` also provisions membership during the first seed. Existing seeds are unchanged by rerunning seed; use `provision-owner` when credentials are configured later.

To test real seller authentication, set `DEMO_MODE=false` and `NEXT_PUBLIC_DEMO_MODE=false`. Rebuild the dashboard because Next.js embeds public environment settings at build time. This disables the local fixture endpoints and demo-token bypass.

For hosted PostgreSQL, use its trusted server connection string, run Alembic migrations first, and preserve RLS/private agent schemas. Do not expose database credentials through browser variables.

## Twilio WhatsApp testing

Twilio is opt-in: set `WHATSAPP_PROVIDER=twilio` explicitly. Keeping its credentials in `.env` does not enable it while another provider is selected. Provider changes do not reroute existing conversations.

Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, the testing environment's actual `TWILIO_WHATSAPP_FROM` and `TWILIO_MERCHANT_ID=SELLER001`. Copy the sender number and join code from your own console; the new Console's trial environment can use a different number from the legacy Sandbox.

In Twilio One Console, open Home → Send a WhatsApp message, activate the testing environment, select the verified tester, and link that phone using the displayed join command. After connection, open Receive a message → Inbound message settings → Custom, enter the incoming webhook URL, and save. Verify the “Webhook configured successfully” confirmation. A standard Twilio auto-reply confirms Twilio received a message; it does not prove RescueLoop received it. See [Twilio's current receiving instructions](https://help.twilio.com/articles/55716571409819-How-do-I-receive-WhatsApp-messages-while-testing).

Check the account's trial capabilities before relying on it for an AI demo. Twilio's current One Console trial documentation requires preset `ContentSid` templates for outbound WhatsApp API messages and does not support direct TwiML response XML. RescueLoop sends custom text through the Messages API, so full live acceptance requires an account/environment that supports those replies. Webhook configuration alone does not establish this capability. See [current WhatsApp trial limitations](https://www.twilio.com/docs/usage/trials/try-out-whatsapp).

For accounts using the legacy Console, use Sandbox settings → When a Message Comes in. See [Twilio Sandbox setup](https://www.twilio.com/docs/whatsapp/sandbox).

Use a reachable HTTPS origin in `PUBLIC_WEBHOOK_URL`, without a path. Configure incoming messages as POST to:

```text
https://YOUR_ORIGIN/webhooks/twilio/incoming
```

The send adapter supplies the status callback:

```text
https://YOUR_ORIGIN/webhooks/twilio/status?local_id=THE_SAVED_MESSAGE_ID
```

The configured external origin must exactly match the one Twilio signs, including any query string. Incoming requests are checked with Twilio's RequestValidator: [webhook security](https://www.twilio.com/docs/usage/webhooks/webhooks-security).

Public policy questions and human handoff can be tested from an unlinked phone. For an order-specific demo, explicitly link the verified test phone to the intended synthetic customer through authenticated `POST /api/customers/link`, with `customer_id` and E.164 `phone`. Never enter a real phone into a public source file. An unlinked sender receives only public catalog/policy assistance and cannot access another customer's orders.

The implementation sends only inside the 24-hour customer-service window. Outside it, messages wait for another inbound message. Sandbox sends are paced. Actual free-form delivery, media retrieval, status receipts and seller follow-ups must be observed; a configured key is insufficient.

## Restart after configuration

```powershell
.\scripts\stop-local.ps1
.\scripts\start-local.ps1 -Build
```

Use `-LocalVerification` if you want to keep exercising synthetic local flows while credentials are unfinished. It overrides provider access only for the launched processes, preserving `.env`.

## Live acceptance checklist

- A seller can sign in with Supabase and is scoped to the correct store.
- The private bucket accepts an image; a foreign/unauthenticated caller cannot retrieve it.
- The configured Groq models routes text and assesses an image; failures do not become simulated AI success.
- A joined WhatsApp phone reaches the signed webhook, and a real reply obtains a delivered/read receipt.
- A seller decision causes exactly one follow-up, with separate customer confirmation.
- Duplicate events, an unavailable provider and a closed messaging window preserve safe state.
- Actual provider latency and any delivery constraints are recorded.

Render and Docker files are deployment templates until an actual deployment is verified. Hosted staging and production require real authentication and provider configuration. Payment and courier providers remain simulated within this approved scope.

## Free hosted demo

The free deployment layout is Vercel Hobby for the seller dashboard, one Render Free web service for the API and worker, and the existing Supabase PostgreSQL database. `infra/render.yaml` explicitly requests `plan: free`; it creates no paid worker, disk or database. The API and worker are supervised together with `python -m app.hosted`, which terminates the container if either process exits.

This is a staging demo, not an always-on production service. [Render Free services](https://render.com/docs/free) can sleep when idle; both the API and worker stop during that time. Delayed jobs resume after wake-up. A new inbound webhook can incur a cold start and provider retries. No artificial keepalive or paid upgrade is configured. Provider API quotas still apply independently.

1. Save the existing Supabase **Session pooler** PostgreSQL URI as `HOSTED_DATABASE_URL` in the ignored root `.env`, with `sslmode=require`. This operator-only value does not automatically replace local `DATABASE_URL`. Use session mode rather than transaction mode because the workflow uses session advisory locks and prepared statements. See [Supabase connection options](https://supabase.com/docs/guides/database/connecting-to-postgres).
2. Inspect the hosted destination before migration. Back up the current local database and preserve all messages, cases, counters, audit rows and private workflow checkpoints. Import into an empty application schema only; do not overwrite existing hosted records. Do not run reset or fresh seed as a substitute for migrating the existing conversation history.
3. Apply/verify Alembic head `0007` and verify imported record counts before starting workers. Keep the old local database as a recovery copy. Coordinate the webhook cutover and stop the old worker so two independent copies cannot both process the conversation.
4. Create the backend from `infra/render.yaml` on the Free plan. Set its `DATABASE_URL` to the hosted URI and copy only the required Groq, Supabase and 360dialog settings into Render's private environment settings. Keep `APP_ENV=staging`, `DEMO_MODE=false`, `AI_MODE=groq` and `WHATSAPP_PROVIDER=360dialog_sandbox`. The entry point derives the public webhook origin from Render's `RENDER_EXTERNAL_URL`; it never prints the private callback token. Twilio remains available in code but disabled.
5. On Vercel Hobby, use repository root directory `apps/seller-dashboard`, the Next.js framework, and Node.js 24. Set build-time `NEXT_PUBLIC_API_URL` to the hosted backend HTTPS origin, `NEXT_PUBLIC_DEMO_MODE=false`, and the existing Supabase public URL/anon key. Never put backend credentials in a `NEXT_PUBLIC_` setting. Permit the exact seller-dashboard origin in backend `CORS_ORIGINS`.
6. Verify the hosted health endpoint, refusal of unauthenticated seller API requests, real seller sign-in, saved cases, private evidence, and the worker heartbeat. Register the existing 360dialog private callback at the hosted origin only after the database and worker are ready. Do not replay failed or uncertain sends automatically.
7. Live WhatsApp verification still needs an actual customer message and its delivered reply. A successful deployment does not remove the Sandbox's exhausted quota or add audio/media retrieval.

`.dockerignore` and `.vercelignore` exclude local credentials, runtime logs, virtual environments and build artifacts. The Docker image uses the backend lockfile. The hosted entry point does not seed, migrate, reset or change webhooks on startup.


## Temporary WhatsApp tunnel

The official Cloudflare helper is kept in the ignored `.local/bin/cloudflared.exe` folder. Its downloaded release checksum was verified. Run `scripts/start-whatsapp-tunnel.ps1` to allocate an HTTPS origin, save `PUBLIC_WEBHOOK_URL`, and start the restricted gateway on loopback port 8003. Restart the main API and worker afterward. Update the Sandbox incoming webhook to that origin plus `/webhooks/twilio/incoming`, using POST.

The gateway has no seller APIs, Swagger or OpenAPI endpoint. Twilio signatures remain mandatory. Run `scripts/stop-whatsapp-tunnel.ps1` to stop the gateway and tunnel. The generated URL changes after a new tunnel is started. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

## 360dialog Sandbox optional provider

The [official Sandbox guide](https://docs.360dialog.com/docs/get-started/sandbox) supports free-form text to one fixed tester. Its allowance is 25 messaging API requests, including rejected sends. Media upload/retrieval by ID is unavailable. This adapter permits development and authenticated staging demos, and preserves the application's 24-hour customer-service window. Production mode still rejects the Sandbox.

1. Send `START` from the tester's WhatsApp to the number in the current official guide (verified 11 November 2026: `+551146733492`). Store the returned key locally as `D360_API_KEY`.
2. Set `WHATSAPP_PROVIDER=360dialog_sandbox`, `WHATSAPP_MERCHANT_ID=SELLER001`, and `D360_SANDBOX_RECIPIENT` to the exact digits-only phone number bound to the key. If the response instead supplies a business-scoped user ID, use that ID and `D360_RECIPIENT_TYPE=bsuid`; otherwise use `phone`.
3. Set `D360_WEBHOOK_SECRET` to a randomly generated URL-safe token of at least 32 characters. Keep it out of chat, Git, screenshots and logs. The callback is `/webhooks/360dialog/<private-token>`. The Sandbox guide documents URL registration without a webhook signature or custom-header mechanism; the random URL token is a bearer credential, not a claimed provider signature.
4. Apply Alembic migration `0006` using the existing database connection. It adds conversation provider/recipient fields and durable receipts, permits unidentified phone numbers for BSUID testers, and preserves existing records. Back up before migrating. Existing conversations remain pinned to Twilio.
5. Start the existing restricted HTTPS gateway. Use `scripts/restart-messaging-backend.ps1` after configuration/code changes to restart only recorded API/worker/gateway processes while preserving the dashboard and current tunnel.
6. Run `services/backend/.venv/Scripts/python.exe scripts/configure_360dialog.py --configure`. It validates the gateway, verifies rejection of an invalid token, registers the private URL using `D360-API-KEY`, and checks the provider's response without printing the key or full callback URL. Re-run registration after a tunnel-origin change. It sends no WhatsApp message.
7. Send `What is your return policy?` from the bound phone. Verify the saved incoming message, `agent.reply_generated` Groq audit entry, accepted outbound provider ID and delivered/read receipt for that exact reply. An HTTP 201 response alone does not prove delivery. Until this chain is observed, live WhatsApp remains unverified.

Only the bound tester is accepted. Unknown customers receive public information; order access still requires the existing explicit seller linkage. The dashboard continues using real Supabase authentication and private evidence storage. An unsupported media event creates a flagged case rather than pretending an image was analyzed. Errors, timeouts and provider switching preserve the existing retry and handoff protections.

Twilio credentials remain intact. Set `WHATSAPP_PROVIDER=twilio` and restart the messaging backend to opt back in; its signature verification and sender checks remain required. `WHATSAPP_PROVIDER=disabled` turns off both incoming provider routes and outbound transport. Jobs belonging to a disabled provider wait for deliberate recovery; they are never sent through the other provider.
