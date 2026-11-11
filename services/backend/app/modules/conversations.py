import re
from fastapi import HTTPException
from sqlalchemy import select
from app.db.models import Case, Customer, Message, Order, Product, Review, now
from app.modules.common import audit, reply, scoped
from app.modules.commerce import KINDS, amount, create_case, confirm_case, confirmation_text
from app.workflows import orchestrator
from app.agents.router import localize_reply


def receive(db, conv, text: str, message_id: str):
    existing = db.get(Message, message_id)
    if existing:
        if existing.conversation_id != conv.id:
            raise HTTPException(409, "Message identifier already used")
        return {"duplicate": True, "reply": "Message already processed"}
    db.add(Message(id=message_id, conversation_id=conv.id, role="customer", body=text, status="received"))
    conv.last_inbound_at = now()
    db.flush()
    if conv.handoff:
        audit(db, conv.merchant_id, "system", "message.held_for_seller", message_id)
        return {"duplicate": False, "reply": "Saved for your seller. Automated replies are paused."}
    confirmation = re.fullmatch(r"\s*(confirm|decline)\s+([\w-]+)\s*", text, re.I)
    if confirmation:
        try:
            with db.begin_nested():
                answer = confirm_case(
                    db, confirmation.group(2), conv, confirmation.group(1).lower() == "confirm"
                )
        except HTTPException as exc:
            answer = str(exc.detail)
        reply(db, conv, answer)
        return {"duplicate": False, "reply": answer}
    if text.strip().lower() in {"yes", "confirm", "ಹೌದು"}:
        ready = list(
            db.scalars(select(Case).where(Case.conversation_id == conv.id, Case.status == "pending_customer"))
        )
        answer = (
            f"Please confirm the specific request by replying CONFIRM {ready[0].id}."
            if len(ready) == 1
            else "Please use CONFIRM followed by the request ID from the quotation."
        )
        reply(db, conv, answer)
        return {"duplicate": False, "reply": answer}
    pending_details = db.scalar(
        select(Case).where(Case.conversation_id == conv.id, Case.status == "needs_details")
    )
    if pending_details:
        pending_details.details = {**pending_details.details, "customer_clarification": text}
        pending_details.status = "pending_seller"
        answer = "Thank you. Your additional details have been sent to the seller for review."
        reply(db, conv, answer)
        audit(db, conv.merchant_id, f"customer:{conv.customer_id}", "case.clarified", pending_details.id)
        return {"duplicate": False, "reply": answer}
    # An order number is never sufficient proof of ownership.
    mentioned = re.search(r"\bORD\d+\b", text, re.I)
    if mentioned:
        selected = db.scalar(
            select(Order).where(
                Order.id == mentioned.group().upper(),
                Order.customer_id == conv.customer_id,
                Order.merchant_id == conv.merchant_id,
            )
        )
        if selected is None:
            answer = "I could not verify that order for this WhatsApp account. Please contact the seller."
            reply(db, conv, answer)
            return {"duplicate": False, "reply": answer}
        conv.order_id = selected.id
    order = db.get(Order, conv.order_id) if conv.order_id else None
    history = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc())
            .limit(8)
        )
    )
    context = (
        f"Order: {order.id if order else 'none'}, status: {order.status if order else 'none'}. Recent conversation: "
        + " | ".join(f"{m.role}: {m.body}" for m in reversed(history))
    )
    try:
        flow = orchestrator.workflow.invoke(
            {"text": text, "context": context}, {"configurable": {"thread_id": f"{conv.id}:{message_id}"}}
        )
    except Exception:
        audit(db, conv.merchant_id, "system", "agent.failed", message_id)
        answer = "I could not process that request right now. Your message is saved; please try again or ask for a human."
        reply(db, conv, answer)
        return {"duplicate": False, "reply": answer}
    proposal = flow["proposal"]
    customer = db.get(Customer, conv.customer_id)
    customer.language = proposal.get("language", "en")
    intent = proposal["intent"]
    audit(db, conv.merchant_id, flow["specialist"], "agent.proposed", message_id, intent=intent)
    if intent == "catalog":
        products = db.scalars(select(Product).where(Product.merchant_id == conv.merchant_id))
        answer = "Available products: " + "; ".join(
            f"{p.name}: {amount(p.price_paise)} ({p.stock} in stock)" for p in products
        )
    elif intent == "tracking":
        answer = (
            f"Order {order.id}: {order.delivery_status.replace('_', ' ')}. Order status: {order.status.replace('_', ' ')}."
            if order
            else "Please share your order ID so I can verify it."
        )
    elif intent == "handoff":
        conv.handoff = True
        answer = "I've handed this conversation to your seller. Automated replies are paused until they return control."
    elif intent == "complaint":
        answer = "Please send a clear product photo. I can help you request a return, replacement, refund, or warranty review after checking your order."
    elif intent == "feedback" and order:
        rating = proposal.get("rating")
        if rating and 1 <= rating <= 5:
            customer = db.get(Customer, conv.customer_id)
            db.add(
                Review(
                    merchant_id=conv.merchant_id,
                    product_id=order.product_id,
                    author=customer.name,
                    rating=rating,
                    body=text,
                    topic="Customer feedback",
                    source=conv.channel,
                )
            )
            answer = "Thank you. Your review has been saved and shared with the seller."
        else:
            answer = "Please include a rating from 1 to 5 stars with your feedback."
    elif intent in KINDS:
        if order is None:
            answer = "Please share your order ID so I can verify ownership before creating a request."
        elif intent == "redelivery" and not proposal.get("address"):
            answer = "Please provide the delivery address using Address: followed by the full address. I'll ask you to confirm before scheduling."
        else:
            try:
                with db.begin_nested():
                    details = {
                        key: value
                        for key, value in proposal.items()
                        if key not in {"intent", "language", "rating"} and value is not None
                    }
                    case = create_case(db, conv, intent, text, details)
                    answer = (
                        f"Your {intent} request has been sent to the seller for approval. Request ID: {case.id}."
                        if case.status == "pending_seller"
                        else confirmation_text(db, case)
                    )
            except HTTPException as exc:
                answer = str(exc.detail)
    else:
        answer = "I can help with products, customization, pickup, delivery, returns, refunds, and warranty support. What would you like to do?"
    answer = localize_reply(answer, customer.language)
    reply(db, conv, answer)
    return {"duplicate": False, "reply": answer, "intent": intent}
