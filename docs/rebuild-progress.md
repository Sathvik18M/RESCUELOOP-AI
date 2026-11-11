# Rebuild progress

Baseline: main prototype at 4f399b8; implementation branch codex/rescueloop-rebuild.
All 16 approved decisions: [baseline](decisions/approved-baseline.md).

- [x] Preserve prototype and create branch.
- [x] Record specification and apply approved folder structure.
- [x] Database migrations and case/domain workflows.
- [x] Twilio adapter, specialists, private evidence and durable worker.
- [x] Five-section seller portal and generated contracts.
- [x] Isolated PostgreSQL tests, competing transactions and browser walkthrough.
- [x] Setup, run/stop, explicit reset, demo, integration and validation documentation.
- [x] Live Groq text/image, Supabase private storage and real seller session verified.
- [x] Optional 360dialog Sandbox: authenticated incoming webhook → actual Groq-generated text → delivered/read WhatsApp reply, visible in the seller Inbox. Provider-independent adapter, preserved disabled Twilio integration, migration 0006 and 58 backend tests passed.
- [x] Real WhatsApp human request → flagged seller case / AI paused → dashboard seller reply → delivered/read receipts, with handoff and seller audit entries verified.
- [x] Resume AI on the same real conversation → fresh customer question → actual Groq reply with delivered/read receipts. Fixed generation wording rejected by the action-claim guard; 16 focused tests passed. All seven earlier messages and 28 audit records preserved; supervised recovery recorded without resetting retry history.
- [x] Real WhatsApp two-failure escalation: one failure keeps AI active; a second distinct Groq solution is rejected → case flagged / AI paused / transfer read. A later customer message is held for seller with no AI reply. Twelve earlier messages and 58 audit records preserved; explicit per-solution failure audits added and three focused checks passed.
- [x] Wrong-order recovery and 35 support issue response paths. Original and fresh real WhatsApp wrong-item messages received actual Groq replies with read receipts. All 22 earlier messages, 103 audit records and six case counters preserved; 107 backend tests passed. Broader live routing survey was rate-limited and is not claimed complete. See support-issues.md and validation.md.
- [ ] Production deployment remains a separate acceptance item. The current WhatsApp tunnel and 360dialog connection are for development.

- [x] Wrong-item fact retention verified on real WhatsApp with read receipts: same case, recorded products and replacement request, no repeated questions. Groq extracts facts; a verified workflow template reports the saved case status.
- [x] Conversation state and source-aware delivery investigations: migration 0007, structured intent guards, active-case follow-ups, customization and commerce prerequisite checks, idempotent review cases, full conversation and evidence in the seller drawer. Full backend suite: 133 passed; 26 focused checks passed after the final intake-reuse adjustment. Production dashboard build and scoped lint passed.
- [x] ORD1042 source mismatch traced to separate legacy/rebuild seeds, not a proven delivery event. Existing nonreceipt messages linked to a reused seller case; blocked customization/pickup intakes relabelled with audits. All 74 baseline messages, 276 audits, 28 case counters and order values preserved.

The user is entering credentials locally. Do not classify configured, synthetic or simulated checks as live acceptance. See [validation status](validation.md).
