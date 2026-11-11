# Release boundary

The authoritative scope is the [16 approved decisions](decisions/approved-baseline.md). The old prototype is preserved on main at 4f399b8; this rebuild uses a separate database and branch.

Included: five seller screens, WhatsApp transport adapter, policy-controlled proposals, case lifecycle and metrics, independent customer consent, durable jobs, private evidence, handoff, inspection/refunds, inventory/pickup consistency, source-linked insights and synthetic demo data.

Local verification is usable without provider credentials. Real Groq, Supabase Auth/Storage and Twilio Sandbox acceptance requires the user's configuration and observable live results. Configuration alone does not establish readiness. The implementation does not silently substitute demo results when a live provider fails.

Payments, delivery bookings and collection payments remain explicitly simulated. This is a hackathon implementation; no public hosting, payment processor integration or courier production deployment was performed.

See [validation](validation.md), [integration setup](deployment.md) and [demo walkthrough](demo.md).
