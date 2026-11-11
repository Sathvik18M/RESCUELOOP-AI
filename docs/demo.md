# Seller dashboard walkthrough

Open [the local seller portal](http://127.0.0.1:3100). Local verification uses synthetic conversations. Live customers use their own WhatsApp application; there is no customer simulator in the portal.

## Starting state

A fresh seed has 12 cases: 6 resolved, 4 ongoing, 2 flagged. The chart and metrics are calculated from saved records. The date filter uses case creation dates in Asia/Kolkata.

| Conversation | Customer | Order | Initial purpose |
| --- | --- | --- | --- |
| CONV001 | Aarav Sharma | ORD1042, headphones ₹1,999 | Above-limit refund, photo review |
| CONV002 | Ananya Rao | ORD1043, wallet ₹799 | Engraving and birthday wrap |
| CONV003 | Riya Mehta | ORD1044, cable ₹199 | Return awaiting inspection |

The browser walkthrough performed during the rebuild leaves completed examples saved. At its end, there are 13 cases: 9 resolved, 3 ongoing, 1 flagged. There is an unpublished example policy draft and a generated report. Published demo rules remain version 1.

## Customization and pickup

1. Open the wallet customization from Overview or Requests. Review the ₹199 engraving, ₹149 wrap, one-day preparation and ₹1,147 proposed total.
2. Approve the proposal. The case becomes pending customer; the order remains ₹799 and unpaid.
3. In local verification, send `CONFIRM Rxxxxxx` using the actual short reference shown in the case:
   `scripts/demo-message.ps1 -Conversation CONV002 -Text 'CONFIRM Rxxxxxx'`.
4. The saved total becomes ₹1,147. Payment remains zero. Duplicate confirmation cannot repeat the charge.
5. Send `Can I collect the wallet tomorrow afternoon?` through the same CLI fixture or real WhatsApp after live setup.
6. Approve the dated pickup window, then confirm its new reference. Stock moves 18 physical / 0 reserved / 18 available to 18 / 1 / 17.
7. Mark ready, enter the customer's six-digit code and complete handover. The demo records ₹1,147 simulated payment, stock becomes 17 / 0 / 17, slot capacity is released and the case resolves after its follow-up. Cancellation instead releases both holds.

## Return and refund

1. In Requests, open HIST009 for the returned cable.
2. Record an accepted inspection with a note. Leave restock unchecked for defective stock.
3. A ₹199 simulated refund proposal appears under the ₹250 limit. Approval, receipt and refund execution remain separate.
4. Confirm the new reference through CONV003. The worker executes the simulated refund and saves its follow-up.
5. The order's refunded amount becomes ₹199; no real money moves. A real WhatsApp case resolves only after delivered/read acknowledgment.

## Private photo review

The seeded headphone case exceeds the automatic refund limit. Upload the synthetic fixture through the authenticated fixture API or send a real photo after connecting WhatsApp. The local mode explicitly does not perform visual analysis.

The case drawer shows private evidence and why manual verification is required. Approval is rejected until required evidence is verified. The seller must record an accepted return inspection or an explicit waiver with a reason before a direct refund proposal. The customer still must confirm.

## Handoff, policies and insights

- Inbox: Take over enables a store-team reply and pauses AI. Resume AI is explicit. Operational stages and unsuccessful-solution counts survive handoff.
- Two distinct failed solutions escalate with complete history. A repeated complaint about the same solution counts once.
- Policies: edit structured fields or ask for a draft. Review the diff before publication. The example ten-day draft is deliberately unpublished; the seven-day rule stays active.
- Insights: generate a range-bound report. Each recommendation links to source cases; three distinct cases are required for a recurring theme. Creating a draft from a recommendation cannot publish it.
- A post-resolution `4 stars` message stores one active rating. A later correction updates the same rating and appends an audit event.

## Screenshots

- [Fresh-seed overview](screenshots/overview-desktop.png)
- [Customization consent](screenshots/customization-flow.png)
- [Completed pickup](screenshots/pickup-complete.png)
- [Completed simulated refund](screenshots/refund-complete.png)
- [Unpublished policy review](screenshots/policy-draft.png)
- [Mobile overview](screenshots/overview-mobile.png)

To restore the starting distribution, use the explicit stop/reset/seed procedure in the README. Seeding alone never erases the walkthrough.
