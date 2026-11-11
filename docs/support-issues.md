# Customer issue response guide

All 35 issue categories have a saved case and a response path. These are next-step instructions, not promises that an action or refund has completed. Groq can phrase the support acknowledgement; the backend controls ownership, approvals, consent and operations.

| ID | Customer issue | Example WhatsApp message | Expected next step |
| --- | --- | --- | --- |
| 01 | Order not confirmed | I paid, but my order isn't confirmed. | Please share your order reference, or payment reference if no order exists, so the store can reconcile payment and confirmation. |
| 02 | Wrong order details | My order has the wrong product. | Please share the order reference and tell us which product you intended to order and which product appears on the order. The store must verify any correction. |
| 03 | Order cancellation | I want to cancel my order. | Please share your order reference. Cancellation eligibility depends on the verified order and the store's policy; any proposed action needs your confirmation. |
| 04 | Order modification | Can I change the size after ordering? | Please share the order reference, current size and requested size. The store must check availability and fulfillment before proposing a change. |
| 05 | Duplicate order | I accidentally ordered the same item twice. | Please share both order references and identify which one you want to keep. The store must verify them before proposing any cancellation or refund. |
| 06 | Delayed delivery | My order hasn't arrived yet. | Please share your order reference so we can check the saved delivery status. A new delivery date cannot be promised without confirmation. |
| 07 | Failed delivery | The delivery person couldn't find my address. | Please share your order reference and the corrected delivery details. A verified failed delivery and your confirmation are required before arranging another attempt. |
| 08 | Wrong delivery address | I entered the wrong address. | Please share your order reference and the address correction. The store must check whether the shipment can still be changed. |
| 09 | Missing package | Tracking says delivered, but I haven't received it. | Please share your order reference and whether anyone at the delivery address received the package. The store must investigate the delivery discrepancy. |
| 10 | Reschedule delivery | Can you deliver tomorrow instead? | Please share your order reference and preferred delivery date. The store must check availability before confirming a new date. |
| 11 | Store pickup request | Can I collect my order from your shop? | Please share your order reference and preferred pickup time. The store must approve availability and you must confirm the pickup terms. |
| 12 | Incorrect delivery status | The tracking information is wrong. | Please share your order reference and explain which tracking update is incorrect. The store must verify the discrepancy. |
| 13 | Damaged product | My headphones arrived broken. | Please share your order reference and describe the damage. The store will check evidence and policy before proposing a remedy. |
| 14 | Defective product | The device isn't working. | Please share your order reference, the product and what happens when you use it. Evidence and eligibility must be checked before proposing a remedy. |
| 15 | Wrong product received | I ordered black but received blue. | Save ordered/received descriptions and the requested remedy. Ask only for missing facts, verify ownership and the actual order, check policy and shipment evidence, and reuse the verification case for seller review. |
| 16 | Missing items | One item is missing from my package. | Please share your order reference and list the missing items and what arrived. The store must check the packing and order records. |
| 17 | Poor product quality | The material quality is bad. | Please share your order reference and describe the quality problem. The store must compare the evidence with the published policy before deciding a remedy. |
| 18 | Product not as described | The product doesn't match the website photos. | Please share your order reference and explain how the received product differs from its description. The store must review the listing and evidence. |
| 19 | Return request | I want to return this product. | Please share your order reference and the reason for returning it. Eligibility, evidence and the published return policy must be checked before you confirm any return. |
| 20 | Refund request | I want my money back. | Please share your order reference and refund reason. Refunds depend on verified payment, eligibility, inspection and the store's approval rules. |
| 21 | Refund delayed | My refund hasn't arrived. | Please share your order reference and any refund reference. The store must check the recorded refund status before providing an update or timeframe. |
| 22 | Refund amount incorrect | I received only ₹500 instead of ₹800. | Please share your order or refund reference and the expected and received amounts. The store must reconcile them before considering an adjustment. |
| 23 | Replacement request | Can you replace my damaged watch? | Please share your order reference and describe the damage. Replacement eligibility and evidence require review before terms can be offered. |
| 24 | Return pickup problem | Nobody came to collect my return. | Please share your order or return reference and the scheduled collection date. The store must check the collection arrangements. |
| 25 | Payment deducted, order missing | Money was deducted, but no order was created. | Please share the payment reference, payment date and amount, plus any order reference you received. The store must reconcile the payment before confirming an order or remedy. |
| 26 | Double payment | I was charged twice. | Please share your order reference and the two payment references with their amounts. The store must verify a duplicate charge before deciding any adjustment. |
| 27 | Incorrect charges | Why was I charged an extra ₹200? | Please share your order reference and identify the unexpected charge. The store must compare the bill with the agreed total. |
| 28 | Invoice issue | I need a GST invoice. | Please share your order reference and any business billing details needed on the invoice. The store must check the invoice records and issue or correct the document. |
| 29 | Customization request | Can you engrave my name on this wallet? | Please share the order reference and exact engraving text. New customization needs a seller decision and your confirmation of the quoted terms. |
| 30 | Incorrect customization | You printed the wrong name on my gift. | Please share your order reference and the requested text versus the text received. The store must compare the saved customization terms and evidence. |
| 31 | Missing customization | I paid for gift wrapping, but it wasn't included. | Please share your order reference and describe the missing customization. The store must verify the agreed customization and payment records. |
| 32 | Custom order delay | My personalized order isn't ready. | Please share your order reference. The store must check the agreed preparation time and current progress before promising a ready date. |
| 33 | Warranty claim | My product stopped working during warranty. | Please share your order reference and describe the fault. The store must check purchase details, warranty coverage and evidence. |
| 34 | Unsatisfactory support | Your previous solution didn't fix my problem. | Please identify the unresolved request or order so we can review the previous solution without counting repeated complaints as new failed solutions. |
| 35 | Human assistance | I want to speak directly with the seller. | A human support request transfers the conversation to the store team and pauses automated replies. |

## Operational rules

- Conversation context persists the active order/case, case-scoped customer facts, pending questions and confirmed completed operations. A greeting does not answer a pending question. Clear follow-ups select the relevant active case; genuine ambiguity names the matching requests.
- Neutral order-status questions use a status lookup. Nonreceipt or requests for delivery location/proof use a delivery-dispute case. A saved DELIVERED status is not proof of customer receipt; missing courier evidence is reported as unavailable and escalated.
- Customization remains an intake until the order is an eligible draft, product options allow the request, and required details are present. Other commerce actions also check eligibility before creating actionable requests. No change is claimed from a proposed action or model response.
- Unknown WhatsApp identities receive public information or requests for verification; an order reference alone does not establish ownership.
- Reports of wrong products, missing items, billing discrepancies or bad customization do not implicitly request a refund, replacement or cancellation.
- Existing action requests retain seller approval, current policy checks and exact customer confirmation. Additional manual-review categories do not introduce payment, courier or invoice integrations.
- Two distinct failed solutions escalate; duplicate complaints and technical retries do not increase that counter. Handoff pauses automated customer replies until the seller resumes AI.
- Terminal incoming-processing failures save the case and audit reason, and queue one idempotent system notice unless the conversation is already under seller handoff. This is labelled as a service problem, never as an AI-generated success.
- Groq structured-output validation errors use the existing three-attempt worker budget. Other invalid requests remain permanent. Rate-limit waits honor Retry-After, including fractional seconds.
- The 360dialog Sandbox cannot retrieve photos for AI analysis. Customers are asked for a text description; seller review remains available. Providers that support image retrieval use the existing vision/evidence workflow, and unclear evidence flags the linked case.

## Verification boundary

The automated suite checks response handling for all 35 categories, ownership boundaries and preservation of unrelated counters. Live WhatsApp verification is recorded separately in validation.md; passing local tests is not a claim that all 35 examples were individually sent through WhatsApp.

Groq structured-output configuration follows [official Groq documentation](https://console.groq.com/docs/structured-outputs). No credentials belong in this guide.
