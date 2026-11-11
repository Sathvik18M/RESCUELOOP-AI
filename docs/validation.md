# Rebuild validation — 11 November 2026 (Asia/Kolkata)

This report distinguishes observed local results from live integration acceptance.

## Passed

- Real 360dialog human handoff verified at approximately 23:22 IST: the customer's “I need human support.” message created a flagged Handoff case and set seller handling. The transfer acknowledgement obtained a read receipt. A seller reply entered through the authenticated dashboard was accepted, delivered and read on the same WhatsApp conversation. `conversation.handoff` and `seller.replied` audit entries are present; no assistant replies were generated after the handoff request. The case remains flagged/investigating and AI remains paused for the seller.
- Real 360dialog Sandbox customer-initiated text flow verified at approximately 23:12 IST: incoming “What is your return policy?” persisted, Groq `openai/gpt-oss-20b` generated the exact customer-received answer, and the matching outbound message obtained sent, delivered and read receipts. The generation audit records the input/output IDs, model and response hash. The case resolved after delivery; the authenticated seller Inbox visibly shows the conversation, Read status and resolved policy case. The user also confirmed receipt.
- Supabase browser seller sign-in passed, with the local seller dashboard reached using the real account; provider credentials, public Auth key, confirmed seller UUID, private upload, signed download and denied unsigned/public access also passed. The existing synthetic evidence thumbnail was visibly rendered in the signed-in case drawer.
- Live Groq structured text routing, resolution/shopping specialists, policy drafting and insights (GPT-OSS 20B), plus image assessment (Qwen 3.8 27B), using synthetic inputs.
- Live Supabase private bucket setup, application upload, signed download, denied unsigned/public access, and synthetic probe cleanup. The explicitly approved configured seller membership and existing synthetic photo copy are complete.
- WhatsApp-only gateway tests reject unsigned callbacks and expose no seller endpoints. A temporary Cloudflare tunnel now reaches the WhatsApp-only gateway. Public health returns 200, seller APIs/docs return 404, and unsigned incoming/status requests return 403. A signed synthetic callback for an unknown message returns 200 without changing business records.
- Twilio authentication passes for the active trial account. Two correct join messages from the selected verified test phone are confirmed received in Twilio's Messages API; the first standard auto-reply was observed as read in its console logs. These are Twilio-hosted messages, not RescueLoop replies.

- Production Next.js build and TypeScript type check.
- 58 backend workflow/integration-boundary tests against isolated PostgreSQL, including the original 48 plus provider isolation, 360dialog webhook authentication/deduplication, BSUID ownership boundaries, window expiry, early delivery receipts, free-form transport, quota exhaustion, unsupported media, secret-log protection and Groq reply provenance.
- Alembic head 0006. The local database was backed up before applying the additive provider migration, and all existing business and audit record counts were preserved.
- Actual competing PostgreSQL transactions: exactly one of two pickups obtained the last stock unit / slot; competing refunds could not reserve more than the paid balance.
- Local API, worker and dashboard startup; stop/restart scripts checked. First-start checkpoint migration race fixed with an advisory lock.
- Browser walkthrough: seller approval → independent synthetic customer confirmation → ₹1,147 customization total with payment still zero.
- Browser walkthrough: pickup approval / consent → reserved → ready → code-verified collection, simulated payment and resolved case.
- Browser walkthrough: return inspection → consent → worker-driven simulated ₹199 refund → completed follow-up and resolved case.
- Browser guard: approving an unverified photo displays the backend refusal inside the case drawer.
- Browser policy draft review: proposed seven-to-ten-day change stayed unpublished; active rules remained unchanged.
- Browser insights: persisted dated report with source links and backend-derived counts.
- Mobile overview and Inbox checked at 390 × 844 with no page-width overflow. Desktop reviewed at 1440 × 1000.

## Pending / not claimed

- The Sandbox does not support media retrieval; that event follows the tested manual-review path. Live seller handoff, seller reply and subsequent Resume AI are verified with actual WhatsApp delivery receipts.
- Twilio One Console remains on Connect to testing environment after two correct join messages; the custom webhook controls have not appeared and no webhook has been saved. The official legacy Sandbox URL redirects this account to a One Console not-found page.
- After explicit approval, one outbound custom-text diagnostic was attempted at 21:48 IST. Twilio rejected it with HTTP 400 / 21654 (ContentSid Required); no message was accepted or delivered. Current One Console trial documentation requires preset templates for outbound WhatsApp API messages. This account cannot currently demonstrate RescueLoop's custom AI replies. Use a supported account/sender environment before repeating live acceptance. [Twilio trial limitations](https://www.twilio.com/docs/usage/trials/try-out-whatsapp), [error 21654](https://www.twilio.com/docs/api/errors/21654).
- Production deployment; the running tunnel is temporary.
- The rewritten Playwright runner is provided for CI but was not executed in this local session; browser actions were exercised through the available browser-control interface.

Screenshots in docs/screenshots contain synthetic records only. Earlier local walkthroughs used authenticated fixture endpoints. The 360dialog test used actual WhatsApp and its proof is kept in ignored `.local/rebuild-run/360dialog-live-verification.json` and `.local/rebuild-run/360dialog-live-inbox.png`. No money moved.

The saved walkthrough changes the initial cohort from 12 / 6 resolved / 4 ongoing / 2 flagged to 13 / 9 resolved / 3 ongoing / 1 flagged. The README documents an explicit reset to recover the initial distribution.

The verified WhatsApp policy case adds one real conversation and one resolved case, giving 14 total / 10 resolved / 3 ongoing / 1 flagged. Twilio remains implemented with its credentials preserved, but is disabled while `WHATSAPP_PROVIDER=360dialog_sandbox`. The 360dialog API key and private callback token are never included in these reports.

The subsequent real human-support request adds one flagged Handoff case, giving 15 total / 10 resolved / 3 ongoing / 2 flagged. The seller's acknowledgement does not mark that customer issue resolved. Ignored local proof: `.local/rebuild-run/360dialog-handoff-verification.json`, `360dialog-handoff-case.png` and `360dialog-handoff-reply.png`.

## Live Resume AI verification

Verified on 11 November 2026 at approximately 23:34 IST. The seller resumed AI in the same real WhatsApp conversation. A new customer question, "What is your return policy now?", reached the webhook after the resume audit. Its first three automatic attempts failed because generated conditional wording contained "processed", which the public-answer action-claim guard rejects. No reply from those failed attempts was sent.

The generation instructions now explicitly describe policy requirements and avoid the validator's blocked action words. The validator and three-attempt automatic retry limit are unchanged. Six focused public-answer checks and ten messaging-provider checks passed on isolated PostgreSQL; scoped Ruff checks passed. An audited, single supervised recovery attempt retained the original three attempts. The recovered answer was generated by Groq (`openai/gpt-oss-20b`), matched its generation-audit SHA256, and received actual sent, delivered and read receipts. A separately received repeat of the same customer question also received a Groq-generated reply with read receipts.

All seven messages and all 28 audit records captured before Resume AI remain unchanged. New resume, generation, delivery and manual-recovery records were appended. The original seller-assisted Handoff case remains ongoing. The technical failure case was resolved only after verified delivery, marked as assisted, and retains its failure and recovery evidence. AI remains enabled. Proof: `.local/rebuild-run/resume-ai-baseline.json`, `resume-ai-verification.json` and `360dialog-resume-ai.png`.

## Live two-attempt escalation verification

Verified on 11 November 2026 at approximately 23:41 IST in the existing 360dialog WhatsApp conversation. The customer reported that the latest delivered policy answer did not solve the question. The same policy case (#0BD1BB) reopened with `resolution_attempts=1` and AI remained enabled. A further policy question received a distinct Groq-generated answer on that case, with a matching generation audit hash and sent/delivered/read receipts. Rejecting that second answer increased the counter to 2, flagged the case as pending seller, recorded seller involvement and enabled conversation handoff. The transfer announcement received sent/delivered/read receipts.

The customer then sent a further policy question. Its incoming job completed through the handoff branch, with a `message.held_for_seller` audit and no new assistant message or outbound reply. This verified the pause at 23:40:57 IST. The seller subsequently sent a reply (read receipt) and explicitly resumed AI at 23:42:02 IST. Current AI assistance is therefore enabled again, while the case remains flagged and its counter remains 2; the test did not undo the seller's actions. All 12 pre-test messages, 58 pre-test audit records and five pre-test cases remain present; prior message contents/roles and audit contents are unchanged.

Each counted failure now appends `case.resolution_failed` with the customer message ID, rejected solution message ID and resulting counter. The two live records reference two distinct delivered solutions. Three focused isolated-PostgreSQL checks passed for unique-solution counting, human handoff pause and separation from technical retries; targeted syntax/undefined-name lint passed. Broader style lint on these existing files still reports pre-existing import/style issues and was not claimed clean.

A separate customer "wrong order" message during this test hit a Groq HTTP 400 and was preserved with a flagged technical case. It did not increment the policy case's resolution counter and was not retried as part of this escalation test. It was subsequently recovered and live-tested in the support-flow work below.

Ignored local evidence: `.local/rebuild-run/two-attempt-baseline.json`, `two-attempt-first-failure.json`, `two-attempt-second-solution.json`, `two-attempt-verification.json`, `two-attempt-followup-state.json`, `two-attempt-case.png`, `two-attempt-audit.png` and `two-attempt-inbox.png`. The verification snapshot records the pause before the later seller resumption; the follow-up snapshot records the latest state. No customer messages or counter values were fabricated for the live test.

## Wrong-order recovery and 35 support issue paths

Completed across 11–12 November 2026 IST. The original Groq HTTP 400 was intermittent: rolled-back diagnosis subsequently succeeded, and repeated routing checks exposed inconsistent complaint-versus-replacement classification. The original provider body was not retained, so its precise error code is not claimed as established. An explicit 35-issue vocabulary now maps a wrong-item report to support clarification, without inferring a replacement/refund/return request. Grounded Groq replies ask for the order reference and expected-versus-received item, accurately identifying the Sandbox's text-only limitation.

Known structured-output validation failures now use the existing three-attempt durable worker budget; other invalid requests remain permanent. Fractional Retry-After values are honored. A terminal incoming-processing failure saves a linked case and sanitized audit reason and queues one idempotent system service notice, unless seller handoff is active. This notice is not presented as Groq-generated success. No credential, provider or authorization changes were made.

- Full isolated-PostgreSQL backend suite: **107 passed**. Includes response paths for all 35 issues, unverified-customer side-effect protection, wrong-product evidence association, preserved unrelated counters, retry/error notices and the original workflow/provider tests. Targeted correctness lint passed.
- Additional live routing survey: 10/35 examples returned the expected issue/intent; 25 were blocked by Groq rate limits. This was stopped and the prompt shortened. This survey is not claimed as 35 live passes.
- Original real wrong-order message recovered through one audited retry: Groq-generated reply, matching response hash, actual sent/delivered/read receipts, original failed technical attempt retained.
- Fresh real WhatsApp message, "I have got the wrong order help me": new Groq-generated reply on the same wrong-product case, sent/delivered/read receipts and user confirmation. The incoming job completed on its first attempt.
- All **22 prior messages**, **103 prior audit records**, and all six previous case counters remain unchanged, including the policy case at **2**. Only new records were appended and intended processing/recovery status was updated. The recovered technical failure case is closed with audit evidence; the customer issue remains ongoing awaiting details, with zero failed solutions.

See [the response guide](support-issues.md) for each category's next step and limits. Local proof: `.local/rebuild-run/support-issues-baseline.json`, `support-issues-live-verification.json`, `support-issues-live-routing.json` and `support-issues-live-inbox.png`. Image retrieval remains unavailable in the [360dialog Sandbox](https://docs.360dialog.com/docs/get-started/sandbox); the existing vision pipeline requires a provider that can supply image bytes.

## Legacy WhatsApp Sandbox access investigation

Rechecked on 11 November 2026 at approximately 22:49 IST, using the existing signed-in account and without changing credentials, upgrading, or purchasing anything.

- The account API identifies an active Trial account created on 11 November 2026. The One Console product switcher offers Twilio Console, SendGrid and Segment, with no Legacy Console option.
- Opening Twilio's official legacy Sandbox link (`https://www.twilio.com/console/sms/whatsapp/sandbox`) redirects through `console.twilio.com` to `https://1console.twilio.com/not-found?badurl=%2Fconsole%2Fsms%2Fwhatsapp%2Fsandbox`. The browser visibly reports that the requested URL was not found. The legacy Sandbox is currently unavailable through this account's Console.
- The [legacy Sandbox documentation](https://www.twilio.com/docs/whatsapp/sandbox) explicitly permits free-form replies during the 24-hour window opened by a customer's message, including the Sandbox join message. That capability is distinct from the current One Console trial's template restriction; it could not be exercised on this account.
- No webhook or sender configuration was changed and no message was sent during this investigation. The conditional customer-initiated dynamic-reply test was not run because the legacy Sandbox was inaccessible.
- Integrity checks confirm `.env` and the existing Groq, Supabase storage, Twilio webhook/transport and dashboard configuration files are unchanged. The dashboard, FastAPI health endpoint and public WhatsApp gateway health endpoint all returned HTTP 200.

Local proof: `.local/rebuild-run/legacy-investigation-check.json` and `.local/rebuild-run/legacy-sandbox-unavailable.png`. These remain ignored local artifacts.

## Conversation workflow correction — 12 November 2026

| Observed failure | Correction and evidence |
| --- | --- |
| Repeated wrong-item intake | Resolution extraction persists order ID, ordered/received products, complaint type, requested remedy and source message IDs. Exact-text fallback prevents omitted model fields from becoming repeated questions. On real WhatsApp, the corrected reply received sent/delivered/read receipts and reused case #0544E7. Groq performed extraction; the reply was composed from verified saved facts, not represented as free-form Groq output. |
| Premature customization request | Intake checks order ownership, draft status, published policy, product options and required inscription before creating an actionable request. Existing blocked customization and pickup cases were relabelled as inquiries with audits, preserving identities/counters/history. Commerce actions also preflight eligibility before configuration. |
| Status query treated as dispute | Explicit neutral status questions route to ORDER_STATUS/tracking; routing guards prevent history or a wrong issue code from turning them into a dispute. |
| Nonreceipt answered only with DELIVERED | DELIVERY_DISPUTE remains PENDING_VERIFICATION and explains that the saved status is not proof of receipt. The seller must investigate. |
| Ambiguous ongoing requests | Durable conversation context contains active_order_id, active_case_id, known_customer_facts, pending_questions and last_completed_actions. History and case sources are retrieved; clear active follow-ups are selected, while genuine ambiguity lists matching case/order references. Greetings do not continue old requests. |
| Delivery location repeated status | Ownership-scoped shipment lookup returns event sources, location and delivery evidence only if stored. Missing evidence is explicitly unavailable and the suggested seller action requests courier proof. No courier request is falsely claimed sent. |
| Failed attempt versus delivered | Read-only inspection found legacy database `rescueloop`: shipped/failed_attempt, no delivered_at; rebuild `rescueloop_rebuild`: delivered/delivered, with synthetic delivered_at. The original seed and rebuild seed differ. There is no recorded shipment event establishing a transition. Both order records remain unchanged; an audited source discrepancy is attached to the seller cases. |

Migration 0007 adds JSON conversation context and a source-attributed shipment-event table. It does not fabricate/backfill courier events. The full migration chain was verified in a new isolated PostgreSQL database before the additive live-demo migration. Customer ownership, seller permissions, Supabase authentication/storage, Groq configuration, 360dialog credentials, disabled Twilio adapter, consent rules and two-failure counters remain intact.

Validation: **133 backend tests passed** on isolated PostgreSQL, including all seven failure scenarios, multi-turn and multiple-intent routing, missing/available proof, conflicting/legitimate shipment histories, duplicate webhooks, blocked customization/product rules, genuine ambiguity, and automatic-reply handoff protection. After the last case-reuse adjustment, **26 focused context/wrong-item tests passed**. Scoped lint and TypeScript checks passed; a production dashboard build succeeded in `.next-conversation` (separate from the running older build). API, gateway and seller dashboard health checks passed. The final drawer was checked through the authenticated seller session.

Data preservation checks cover **74 prior messages** (body hashes and roles), **276 prior audit records** (full records), **28 case counters**, and all saved order statuses, delivery timestamps, amounts and customizations. All comparisons passed. Three actual nonreceipt/location messages were linked to the reused delivery review case #5BEC39, with no outbound message generated by maintenance. No refund, payment, order modification or courier booking was performed.

Remaining boundary: real courier event history/proof/location is absent, so seller verification is still required. The legacy and rebuild demo datasets are intentionally left unreconciled until the seller establishes an authoritative source. The corrected wrong-item flow was live-tested; the other new conversation scenarios passed regression tests and have not all been repeated as fresh WhatsApp exchanges. The 360dialog Sandbox photo retrieval limitation still applies.

The latest job inspection also found three outbound jobs failed with `SandboxQuotaExceeded` after the earlier successful wrong-item exchange. Their failures, original attempt counts and technical review case #AF9EAD are preserved. The seller portal therefore still reports Processing Delayed. Further real WhatsApp acceptance is blocked by the Sandbox allowance; no quota bypass, credential change, paid upgrade or new provider was attempted.

Local proof: `.local/rebuild-run/wrong-item-workflow-verification.json`, `conversation-workflow-baseline.json`, `conversation-reconciliation.json`, `conversation-workflow-verification.json`, and `conversation-review-case.png`.
