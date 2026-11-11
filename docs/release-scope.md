# First implementation scope

## Available locally

The dashboard is connected to real FastAPI endpoints and PostgreSQL. The four main demonstration journeys are implemented. The support engine also handles cancellation, returns, replacement reservation, warranty claim opening, reviews, seller takeover, policy drafting/publishing, and persisted evidence.

OpenAI and WhatsApp adapters, Supabase JWT/private-storage integration, job processing, database migrations, generated API contracts, deployment files, and CI are included. External-provider credentials were not available during implementation, so live-provider execution is not verified.

## Deliberate limits of v0.1

- The demo store starts with two products and two existing orders, including a wallet draft. New product creation, multi-item carts, variants as separately stocked SKUs, and public seller onboarding are not exposed in this release.
- The catalog editor changes price and available stock. New catalog entries and pickup windows are currently provisioned through seed/import data.
- Custom engraving and novel requests always require seller approval. Reusable customization-rule authoring is a later extension; an earlier one-off approval is never silently reused.
- Pickup slots are named demo windows, not a calendar/date booking engine. The first demo supports one pickup location and one reservation per order.
- Returns, replacements, and warranty claims create operational records; actual courier pickup, exchange dispatch, and warranty-provider processing need real integrations.
- All payment and refund execution is simulated, including in a live-messaging environment. No payment gateway is configured.
- English is the complete deterministic demo path. The demo router recognizes a small set of Kannada keywords. Live OpenAI routing and reply localization support Kannada, but language quality needs live acceptance testing.
- Agent runs are checkpointed; approval waits use persisted domain cases rather than long-running LangGraph interrupt sessions.
- Insights display database counts and an explicit analysis report. External review imports, scheduled trend reports, and reusable policy recommendations are later extensions.
- Authentication expects pre-provisioned Supabase users and membership records. A self-service staff-management screen is not included.
- The dashboard refreshes automatically every eight seconds while visible. There is no websocket service in this release.
- API pagination, generalized product/order import, service-provider performance testing, and live WhatsApp template validation remain follow-up work before broader use.

This implementation establishes a runnable, testable foundation without representing unavailable integrations as active services.
