# Architecture and invariants

The [approved baseline](decisions/approved-baseline.md) governs the implementation. PostgreSQL is the business source of truth. Model output is a proposal, never authorization.

## Message and action flow

1. The selected provider's webhook authenticates and persists incoming messages before queuing existing agent jobs. Twilio uses its signed form request, external origin, account and recipient checks. The optional 360dialog Sandbox uses a private random URL token (its documented Sandbox configuration does not expose a signature option), fixed-tester checks, bounded JSON payloads and provider message deduplication. Disabled providers reject inbound requests.
2. A leased database job serializes incoming messages per conversation. Earlier unprocessed messages block later ones. An unknown phone has no access to seeded orders until an owner explicitly links it.
3. LangGraph coordinates intent extraction. Support and Shopping refine against current authorized records; Photo assesses clarity; Insights cites cases. A case receives its own policy, history, evidence, counters and proposal. Older context is source-linked and cannot establish consent.
4. The domain layer checks ownership, published rules, evidence, balances, stock, slots and permissions. Seller approval and customer consent remain separate. A short reference identifies one revision and exact terms; stale terms require a fresh proposal.
5. A transaction reserves inventory/capacity or refundable balance. Effects have stable operation IDs. The simulated provider records its result. Outbound notification is a separate job.
6. Only delivered/read receipts resolve real WhatsApp cases requiring communication. Synthetic fixtures are explicitly marked `demo_delivered`. Provider acceptance alone does not count as delivery.

The API and worker serialize initial checkpoint migrations with a PostgreSQL advisory lock. LangGraph tables stay in the private `rescueloop_agents` schema.

## State and counters

Primary case states are mutually exclusive: ongoing, flagged, resolved. Operational stages (waiting for consent, return receipt, refund execution, pickup ready, notification) are independent. Seller takeover flags active cases without discarding their operational stage. AI is paused until explicit resumption.

Two distinct unsuccessful solutions trigger escalation. Repeating the same complaint about one solution does not count twice. Technical failures use three total safe attempts, delayed 5 seconds and 15 seconds or a longer provider Retry-After. Neither technical retries nor clarification requests increment the resolution counter.

Technical errors are recorded without secrets. Ambiguous outbound sends are held for verification, not resent automatically. Known provider IDs can be reconciled through the case conversation: Twilio supports status lookup; 360dialog Sandbox uses persisted webhook receipts. Unknown IDs require provider-side verification. Business operations remain committed independently of notification failures. Late receipts can complete the exact pending outcome, but cannot close a subsequently reopened issue.

Conversations persist their messaging provider and recipient separately from customer identity. Switching providers never reroutes existing conversations. BSUID-only Sandbox testers have no inferred phone number or order access. Delivery receipts are saved before an outbound ID is necessarily known and applied after send association, closing the early-callback race. The Sandbox's quota-exhausted response is a permanent failure; ambiguous transport failures still require review. Sandbox media requests are flagged for seller review without downloading unsupported media.

Public catalog and policy answers can be composed by Groq from verified store facts. Their audit entries record the model, input message ID, outgoing message ID and response hash. The existing policy engine, proposal confirmations and business-operation transitions remain authoritative; generation cannot authorize an action.

Sandbox sends are paced globally, with a persisted send marker before the network boundary and another handoff check before sending. Expired 24-hour messaging windows wait for a new inbound message. There is no generic fallback to a simulated success or an arbitrary template.

## Business consistency

- Physical stock minus reserved stock equals available stock. Pickup reserves both stock and slot capacity in one transaction. Collection reduces physical and reserved stock; cancellation releases the holds. Missed windows flag and retain holds.
- Customization consent updates terms and total, without creating a payment. Engraving requires approval. The exact text, price, wrap, preparation and expiry are included in the proposal.
- Accepted return inspection is recorded separately from restocking. Refund proposals obey current permissions, cumulative automatic limits and remaining paid balance.
- Pending and uncertain refunds reserve balance. Definitive failures release it. A confirmed success updates refunded totals once. All demo payment/courier results are explicitly simulated.

## Data and access

FastAPI checks store membership on every seller operation and owner permissions for policy publication and approvals. Supabase JWTs are verified through JWKS. Application tables have RLS with no browser-facing business access policies; trusted backend database roles perform scoped queries.

Images accept JPEG/PNG/WebP, max 8 MB / 20 megapixels, are re-encoded without metadata, and stored privately. Local access requires seller authorization; hosted access uses short-lived signed URLs. Image content is untrusted and cannot authorize refunds. Model clarity and seller verification are distinct facts.

## Metrics and reports

The date filter selects cases by creation date in Asia/Kolkata, using UTC storage. Current statuses add up to the cohort total. Resolution rate is resolved / total. AI share excludes every resolved case with case-specific seller involvement. Median duration includes waiting and reopening. Empty denominators are null. Each case has one active customer rating; corrections add audit events.

Reports are generated on demand, saved with their date range and mode, and cite actual case IDs. Backend code validates IDs and computes distinct-case counts. Three distinct cases establish a recurring theme. Recommendations can create a policy draft but cannot publish it.

## Integration status

Local verification is deterministic and labelled. Live configuration is labelled configured, not treated as proof of live availability. A missing worker or configuration reports unavailable; exhausted/uncertain jobs report delayed. Actual Groq, Supabase and Twilio acceptance remains a separate release gate.
