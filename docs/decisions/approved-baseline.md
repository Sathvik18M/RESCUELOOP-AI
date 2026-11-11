# RescueLoop AI — approved rebuild baseline

Status: approved by the owner in conversation; implementation authorized after Decision 16.
The prototype is preserved in Git on `main`; rebuild branch: `codex/rescueloop-rebuild`.
This document governs differences from the prototype. No public deployment is requested.

## 1. Interfaces
Seller-only minimalist portal: Overview, Inbox, Requests, Policies, Insights. Customer interface is real WhatsApp. Case-level logs, evidence and order context stay inside cases. Overview shows Total, Resolved, Ongoing, Flagged and a chart derived from records. Normal requests are automated; restricted, uncertain, missing-policy and human requests escalate.

## 2. Agent responsibilities
Coordinator routes to Support, Shopping, Photo and Insights specialists. Models may propose; backend validates and executes. Two unsuccessful customer solutions escalate. Human requests transfer immediately. Takeover pauses AI until explicit seller resumption. Approval and customer consent are separate.

## 3. Policies
Structured return/refund/customization/pickup/delivery permissions: automatic-after-consent, seller-approval, unavailable. AI can draft; only seller publishes. Version all policies; recheck current conditions before execution. Missing/conflicting rules flag. Refund limits are cumulative per order. One-off decisions never silently become reusable policy. Material changed terms require fresh approval/consent.

## 4. Persistence and lifecycle
PostgreSQL owns customer, conversation, order/product, case, request, approval/consent, policy, evidence, activity and feedback records. Photos are private objects. Multiple cases may share a conversation/order. Primary statuses are mutually exclusive ongoing/flagged/resolved. Waiting for customer/operations is ongoing; seller handling is flagged. Resolve only after required outcomes and communication. Reopen the same issue. Clarifications and technical retries do not count as unsuccessful solutions. Persist waits, deduplicate events and confirmations.

## 5. Stack and integration boundary
Next.js/TypeScript/Tailwind; FastAPI/Python; LangGraph/OpenAI Responses; PostgreSQL/SQLAlchemy/Alembic; Supabase Auth/private Storage; Twilio Sandbox; PostgreSQL-backed Python worker. Real WhatsApp/model calls and real saved state; payment/courier providers simulated and labelled in customer messages. Seed business data. Local dashboard/API/worker with a verified public HTTPS webhook; Supabase for shared hosted data/auth/storage, Docker PostgreSQL for isolated development. Follow Sandbox join/window/template restrictions. Provider failures never silently become simulated success.

## 6. Layout and staged work
`apps/seller-dashboard/src/{app,features,components,lib}`; `services/backend/app/{api,domain,agents,integrations,persistence,workers,core}` plus migrations/tests; `packages/contracts`; `data/demo`; `scripts`; `infra`; `docs/decisions`. Generate frontend contracts. Keep prompts, migrations and seeds separate. Ignore secrets/runtime artifacts. Preserve baseline, use separate rebuild DB, implement rules then integrations then five-section UI then verification.

## 7. Seller UX
Warm white, readable dark text, green accents, restrained borders; accessible text labels and mobile navigation. Shared case detail shows request/status/order, reason, checks, evidence, proposal/consent, conversation, expandable audit. Preview approval consequences; rejection requires reason; information requests require question. Preserve input on errors. Filter cases by created date, display current statuses. Honest AI availability, loading/empty/error states.

## 8. WhatsApp UX
Natural text/photos; identify, check, explain, confirm, execute, follow up. Sender-to-customer ownership precedes order access. Short human-readable proposal references bound to exact terms; new refs after changes/expiry. Ambiguous acceptance asks clarification. Announce seller escalation only after persistence. Photos link to case; unclear photo flags. Seller messages identify store team. Label simulated actions. No duplicate business action on notification retry. Ask feedback after resolution.

## 9. Access/audit
Pre-provisioned seller Auth and backend store membership. Test WhatsApp identities linked by seller to synthetic records; unknown senders only public data. Scope every API/tool/object. Verify webhooks. Validate images; authenticated/expiring access. Server-only credentials. Untrusted messages/images cannot change permissions. Recheck ownership/consent/policy before effects, handoff before AI sends. Append audit corrections; version policies. Verify uncertain results. Explicit store-specific demo reset must also remove evidence.

## 10. Acceptance and delivery
Business tests, DB/integration tests, browser journeys, and separate actual WhatsApp checks. Verify routing/facts/permissions rather than exact model wording. Demonstrate tracking, return/refund, photo escalation, customization, pickup, feedback, two-failure/human handling. Reconcile analytics. Deliver migrations, all decisions, setup/env/run/stop/reset instructions, walkthrough/screenshots and passed/blocked/not-run report. Live-ready only after actual providers observed; fix consent/data/duplicate/false-success defects first.

## 11. Scope/change handling
Approved decisions are authoritative. Routine implementation choices autonomous. Review material changes to consent/access/retention/sharing, providers/cost/exposure, features or agreed behavior. Check external readiness; complete independent work while unavailable configuration is recorded. Interface-only completion is insufficient.

## 12. Demo configuration
Loop & Co.; INR integer paise, tax-inclusive prices, zero extra delivery. Refund limit 25000 paise cumulative, remaining-paid cap. Seven-day return window; damaged/defective/incorrect-item reasons. Engraving 19900 paise (seller approval), gift wrap 14900, preparation one day. One pickup location, two dated five-capacity slots, seller approval plus consent. Proposals expire 24 hours after issue, separately from messaging window. Return refund after received/accepted unless seller explicitly waives with recorded reason. Products: headphones 199900, wallet 79900, cable 19900. Wallet with engraving/wrap 114700. Twelve synthetic cases across fourteen days: six resolved, four ongoing, two flagged (headphone refund and wallet customization). Actual dated windows; idempotent seed and explicit reset.

## 13. Recovery
Two failed solutions vs three total safe technical attempts. Retry delays 5s then 15s or provider's longer wait. Permanent invalid/permission/config failures stop. Reconcile uncertain effect/send before retry. Save message/job before processing; serialize each conversation; independent conversations may run concurrently. Persist all waits/results; retrying generation cannot repeat effects. Exhausted/uncertain operations flag; no increment to resolution counter. Honest unavailable/delayed/seller states. Configurable timeouts, measured latency.

## 14. Metrics and insights
Created-date cohort in Asia/Kolkata; UTC storage; current statuses sum to total. Resolution rate resolved/total. AI share resolved without case-specific human intervention / all resolved. Median creation-to-latest-resolution among currently resolved, includes reopening/waiting. Null denominators show insufficient data. One active 1–5 rating per case; edits audited; sentiment distinct. Source-referenced reports, backend counts validated references; recurring threshold three distinct cases. On-demand dated/range-bound reports; factual metrics update independently. Recommendation -> policy draft -> explicit publication. No invented comparisons.

## 15. Context and multiple requests
Backend authorized identity, current records/rules, twelve relevant messages, source-referenced older summary, case evidence, pending actions. Database facts outrank summaries. Summaries cannot establish consent/payment/approval. Retrieve source history or clarify contradictions. Split distinct requests into linked cases; reuse same issue; independent consent/failure counters. One concise customer response may cover several requests. Handoffs/restarts/context summaries never reset counters.

## 16. Business consistency
Separate approval, consent and execution. Customization updates terms, not payment. Confirmed pickup atomically reserves stock + capacity, at most one active reservation/order. Physical/reserved/available stock are distinct; 18/1/17 -> collected 17/0/17 or cancelled 18/0/18. Missed window flags and retains hold until collection/cancellation. Return receipt requires inspection; seller decides restock. Pending+completed refunds reduce remaining balance; definitive failure releases, uncertainty retains reservation. Operation state separate from case. Stable operation IDs, persisted results and explicit adjustments. Simulation obeys same state transitions.


## Provider amendment — 11 November 2026

The user requested Groq instead of the OpenAI API during live verification. Groq now supplies all live text and vision generation. Business policy, consent, retry, audit and handoff decisions remain governed by the original baseline. Text defaults to Groq-hosted GPT-OSS 20B; vision uses Qwen 3.8 27B (preview).
