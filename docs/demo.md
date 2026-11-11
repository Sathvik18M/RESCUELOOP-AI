# Four demo journeys

Open the dashboard and select **Enter demo workspace**. The normal seed is idempotent and does not reset prior decisions. Browser tests use a separate database when a fresh demonstration is needed.

## 1. Wallet customization

1. Open **Requests & approvals** and review the existing `CASE1043` request.
2. Quote ₹199 for engraving. Gift wrapping is already configured at ₹149.
3. Approve. Verify that `ORD1043` still totals ₹799 until the customer confirms.
4. Open **WhatsApp inbox**, select **Ananya Rao**, and send `CONFIRM CASE1043` as **Demo customer**.
5. The order subtotal becomes ₹1,147. Review the recorded action in **Action log**.

## 2. Store pickup

1. In Ananya's conversation, send `Can I collect the wallet tomorrow afternoon?`.
2. Approve the pickup request in **Requests & approvals**.
3. Back in the inbox, use **Prepare confirmation**, or copy the specific `CONFIRM <request-id>` command from the reply.
4. Confirm. Stock decreases once, one pickup slot is reserved, and a six-digit collection code is sent.
5. Open **Store pickup**, select **Mark ready**, then **Verify collection** with the customer's code.
6. The order is delivered and the demo collection payment is recorded. A feedback request appears in the conversation.

## 3. Failed-delivery recovery

1. Select **Aarav Sharma** in the inbox.
2. Send `Redelivery please. Address: 12 Demo Road, Bengaluru`.
3. Send the returned `CONFIRM <request-id>` command.
4. `ORD1042` changes from `failed_attempt` to `redelivery_scheduled` and an audit record is created.

## 4. Photo complaint and refund

1. Open **Demo studio** and choose **Photo complaint & refund**. This moves `ORD1042` into the delivered scenario, inside its return window.
2. In Aarav's inbox, attach a JPEG, PNG, or WebP image. The image appears in **Evidence gallery**.
3. In demo AI mode, the assessment explicitly says visual analysis was not run. With configured OpenAI credentials it calls the vision adapter.
4. Send `I want a refund`.
5. The ₹1,999 amount exceeds the ₹250 cumulative automatic-refund cap, so it waits for seller approval.
6. Approve under **Returns & refunds**, then send `CONFIRM <request-id>` as the customer.
7. A simulated refund record is persisted. A repeat confirmation does not create another refund.

The image at `data/demo/assets/test-evidence.png` is a synthetic browser-test fixture, not evidence of actual product damage.
