import re
import json
from time import monotonic
from fastapi import HTTPException
from sqlalchemy import select
from app.persistence.models import (
    Case,
    Customer,
    Conversation,
    Message,
    Order,
    Product,
    Review,
    Policy,
    Evidence,
    Job,
    now,
)
from app.domain.common import audit, reply, scoped
from app.domain.cases import flag, transition, support_case, context_for, remember
from app.domain.commerce import KINDS, amount, create_case, confirm_case, confirmation_text, configure_request
from app.agents.workflows import orchestrator
from app.domain.support_issues import BY_CODE, next_step


def set_handoff(db, conv, enabled, actor):
    conv.handoff = enabled
    for case in db.scalars(
        select(Case).where(Case.conversation_id == conv.id, Case.primary_status != "resolved")
    ):
        if enabled:
            case.seller_assisted = True
            if "handoff_state" not in case.memory:
                case.memory = {
                    **case.memory,
                    "handoff_state": {
                        "primary": case.primary_status,
                        "stage": case.status,
                        "reason": case.flag_reason,
                    },
                }
            transition(db, case, "flagged", case.status, "Seller is handling this conversation.")
        elif "handoff_state" in case.memory:
            prior = case.memory["handoff_state"]
            if case.flag_reason == "Seller is handling this conversation.":
                transition(db, case, prior["primary"], case.status, prior["reason"])
            case.memory = {k: v for k, v in case.memory.items() if k != "handoff_state"}
    for job in db.scalars(
        select(Job).where(Job.kind == "send_message", Job.status.in_(["pending", "waiting_window"]))
    ):
        msg = db.get(Message, job.payload.get("message_id"))
        if enabled and msg and msg.conversation_id == conv.id and msg.role == "assistant":
            msg.status = "held_for_seller"
            job.status = "held"
    audit(db, conv.merchant_id, actor, "conversation.handoff", conv.id, enabled=enabled)


def choose_order(db, conv, text, proposal):
    orders = list(
        db.scalars(
            select(Order).where(Order.customer_id == conv.customer_id, Order.merchant_id == conv.merchant_id)
        )
    )
    mentioned = re.findall(r"\bORD\d+\b", text, re.I)
    requested = proposal.get("order_id")
    if requested:
        mentioned.append(requested.upper())
    if mentioned:
        matched = [o for o in orders if o.id in {x.upper() for x in mentioned}]
        if len({x.upper() for x in mentioned}) != 1 or len(matched) != 1:
            return None
        return matched[0]
    product_hint = (proposal.get("product") or "").lower()
    for term in ("headphone", "wallet", "cable"):
        if term in text.lower() or term in product_hint:
            matches = [o for o in orders if term in db.get(Product, o.product_id).name.lower()]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                return None
    active_id = (conv.context or {}).get("active_order_id") or conv.order_id
    return next((o for o in orders if o.id == active_id), orders[0] if len(orders) == 1 else None)


def case_for_feedback(db, conv, text):
    ref = re.search(r"\bR[0-9A-F]{6}\b", text, re.I)
    stmt = select(Case).where(Case.conversation_id == conv.id, Case.primary_status == "resolved")
    if ref:
        stmt = stmt.where(Case.proposal_ref == ref.group().upper())
    elif conv.order_id:
        stmt = stmt.where(Case.order_id == conv.order_id)
    rows = list(db.scalars(stmt.order_by(Case.resolved_at.desc())))
    # Latest resolved case is the one whose feedback prompt was sent most recently.
    return rows[0] if rows else None


def receive(db, conv, text, message_id):
    from app.domain.conversation_context import hydrate, remember_turn

    prior = db.get(Message, message_id)
    if prior and prior.processed and prior.conversation_id == conv.id:
        return {"duplicate": True, "reply": "Message already processed"}
    hydrate(db, conv)
    result = _receive(db, conv, text, message_id)
    if not result.get("duplicate"):
        remember_turn(db, conv, message_id)
    db.flush()
    return result


def _receive(db, conv, text, message_id):
    started = monotonic()
    msg = db.get(Message, message_id)
    if msg and msg.conversation_id != conv.id:
        raise HTTPException(409, "Message identifier already used")
    if msg and msg.processed:
        return {"duplicate": True, "reply": "Message already processed"}
    if not msg:
        msg = Message(
            id=message_id,
            conversation_id=conv.id,
            role="customer",
            body=text,
            status="received",
            processed=False,
        )
        db.add(msg)
    # Real inbound timestamps belong to provider ingestion, not delayed/retried agent work.
    if conv.channel == "demo":
        conv.last_inbound_at = now()
    db.flush()
    for job in db.scalars(select(Job).where(Job.kind == "send_message", Job.status == "waiting_window")):
        outgoing = db.get(Message, job.payload["message_id"])
        if outgoing and outgoing.conversation_id == conv.id:
            job.status = "pending"
            job.available_at = now()
    if conv.handoff:
        msg.processed = True
        audit(db, conv.merchant_id, "system", "message.held_for_seller", message_id)
        return {"duplicate": False, "reply": "Saved for the seller; automation is paused."}
    answers = []
    associated = []
    confirmation = re.fullmatch(r"\s*(confirm|decline)\s+(R[0-9A-F]{6})\s*", text, re.I)
    if confirmation:
        try:
            with db.begin_nested():
                answer, case, complete = confirm_case(
                    db, confirmation.group(2), conv, confirmation.group(1).lower() == "confirm"
                )
                msg.case_ids = [case.id]
                reply(db, conv, answer, cases=[case], completes=complete)
        except HTTPException as exc:
            answer = str(exc.detail)
            reply(db, conv, answer)
        msg.processed = True
        return {"duplicate": False, "reply": answer}
    if text.strip().lower() in {"yes", "confirm", "accept", "ಹೌದು"} or re.match(
        r"^\s*(confirm|decline)\b", text, re.I
    ):
        refs = list(
            db.scalars(select(Case).where(Case.conversation_id == conv.id, Case.status == "pending_customer"))
        )
        answer = (
            "Please reply CONFIRM followed by the short reference on the exact proposal"
            + (": " + ", ".join(c.proposal_ref or "" for c in refs) if refs else "")
            + "."
        )
        reply(db, conv, answer)
        msg.processed = True
        return {"duplicate": False, "reply": answer}
    if re.search(
        r"still (?:not |un)?resolved|did(?:n't| not|n’t) (?:work|solve|fix)|not solved|still wrong",
        text,
        re.I,
    ):
        candidates = list(
            db.scalars(select(Case).where(Case.conversation_id == conv.id).order_by(Case.updated_at.desc()))
        )
        candidates = [c for c in candidates if c.details.get("last_solution")]
        active = [c for c in candidates if c.primary_status != "resolved"]
        explicit = [
            c
            for c in candidates
            if (c.proposal_ref and c.proposal_ref in text.upper())
            or (c.order_id and c.order_id in text.upper())
        ]
        choices = explicit or active or candidates[:1]
        if len(choices) > 1:
            answer = "Which request is still unresolved? Please include its order or proposal reference so the right case is reopened."
            reply(db, conv, answer)
            msg.processed = True
            return {"duplicate": False, "reply": answer}
        case = choices[0] if choices else None
        if case:
            d = case.details
            solution = d.get("last_solution")
            if solution and d.get("failed_solution") != solution:
                case.resolution_attempts += 1
                case.details = {**d, "failed_solution": solution}
                audit(
                    db,
                    conv.merchant_id,
                    "customer",
                    "case.resolution_failed",
                    case.id,
                    input_message_id=message_id,
                    solution_message_id=solution,
                    resolution_attempts=case.resolution_attempts,
                )
            transition(db, case, "ongoing", "investigating")
            msg.case_ids = [case.id]
            if case.resolution_attempts >= 2:
                set_handoff(db, conv, True, "system")
                flag(db, case, "Two unsuccessful customer resolutions. Complete history is available.")
                answer = "Two solutions have not resolved your issue. I've transferred this conversation to the store team."
            else:
                answer = "I've reopened this case. Please tell me what is still wrong so we can check the next solution."
            reply(db, conv, answer, role="system", cases=[case])
            msg.processed = True
            return {"duplicate": False, "reply": answer}
    from app.domain.wrong_items import should_handle, handle as handle_wrong_item
    # Preserve the specialized extractor for a single wrong-item request. Distinct
    # requests are routed independently below, not swallowed by this shortcut.
    from app.agents.intent_rules import split_requests
    if should_handle(db, conv, text) and len(split_requests(text)) == 1:
        return handle_wrong_item(db, conv, text, message_id)
    orders = list(
        db.scalars(
            select(Order).where(Order.customer_id == conv.customer_id, Order.merchant_id == conv.merchant_id)
        )
    )
    from app.domain.conversation_context import relevant_history, select_continuation
    history = relevant_history(db, conv)
    waiting = list(
        db.scalars(
            select(Case).where(
                Case.conversation_id == conv.id, Case.status.in_(["needs_details", "needs_customer_details"])
            )
        )
    )
    context = json.dumps(
        {
            "conversation_state": conv.context,
            "authorized_orders": [
                {"id": o.id, "product": db.get(Product, o.product_id).name, "status": o.status}
                for o in orders
            ],
            "requests_awaiting_information": [
                {
                    "kind": c.kind,
                    "order_id": c.order_id,
                    "question": c.details.get("seller_question"),
                    "summary": c.summary,
                }
                for c in waiting
            ],
            "recent_messages": [{"id": m.id, "role": m.role, "text": m.body} for m in history],
        }
    )
    flow = orchestrator.workflow.invoke(
        {"text": text, "context": context}, {"configurable": {"thread_id": f"{conv.id}:{message_id}"}}
    )
    proposals = flow.get("proposals", [])
    audit(db, conv.merchant_id, "coordinator", "tool.intent_extracted", conv.id,
        input_message_id=message_id, proposals=proposals)
    if any(p["intent"] == "handoff" for p in proposals):
        proposals = [p for p in proposals if p["intent"] == "handoff"][:1]
    continuation = None
    if len(proposals) == 1 and proposals[0]["intent"] in {"unknown", "complaint"} and waiting:
        continuation = select_continuation(db, conv, waiting, text)
        if continuation is None:
            answer = "Which request is this about: " + "; ".join(
                f"{c.kind.replace('_', ' ')} for {c.order_id or 'unverified order'} (#{c.id[:6].upper()})"
                for c in waiting) + "?"
            reply(db, conv, answer)
            msg.processed = True
            return {"duplicate": False, "reply": answer}
        proposals[0] = {**proposals[0], "intent": "customization" if continuation.kind == "customization_inquiry" else continuation.kind, "order_id": continuation.order_id}
        if continuation.kind == "redelivery":
            proposals[0]["address"] = text
    for p in proposals:
        from app.agents.intent_rules import normalize
        p = normalize(p)
        intent = p["intent"]
        issue = BY_CODE.get(p.get("issue_code"))
        fragment = p.get("request_text") or text
        if intent == "greeting":
            answers.append("Hello. How can I help with your order or ongoing request?")
            continue
        if intent == "wrong_item" or p.get("issue_code") == "15":
            result = handle_wrong_item(db, conv, fragment, message_id)
            associated.extend(db.get(Case, cid) for cid in result["case_ids"])
            continue
        order = choose_order(db, conv, fragment, p)
        if re.search(r"\bORD\d+\b", fragment, re.I) and order is None:
            answers.append(
                "I could not verify that order for this WhatsApp identity. The store team can help verify ownership."
            )
            continue
        if order:
            conv.order_id = order.id
        if intent in {"tracking", "delivery_dispute"}:
            from app.domain.delivery_support import handle as handle_delivery
            answer, case = handle_delivery(db, conv, p, order, message_id)
            if case.status == "status_checked":
                reply(db, conv, answer, cases=[case], completes=True)
            else:
                answers.append(answer)
            associated.append(case)
            continue
        if intent == "customization":
            from app.domain.customization_intake import handle as handle_customization
            answer, case = handle_customization(db, conv, p, order, message_id)
            answers.append(answer)
            associated.append(case)
            continue
        if intent == "feedback":
            rating = p.get("rating")
            case = case_for_feedback(db, conv, fragment)
            if not case or not rating:
                answers.append("Please include a 1–5 star rating after your case is resolved.")
                continue
            prior = db.scalar(select(Review).where(Review.case_id == case.id))
            customer = db.get(Customer, conv.customer_id)
            if prior:
                audit(
                    db,
                    conv.merchant_id,
                    f"customer:{customer.id}",
                    "feedback.corrected",
                    case.id,
                    previous_rating=prior.rating,
                    previous_body=prior.body,
                )
                prior.rating = rating
                prior.body = text
            else:
                db.add(
                    Review(
                        case_id=case.id,
                        merchant_id=conv.merchant_id,
                        product_id=db.get(Order, case.order_id).product_id if case.order_id else None,
                        author=customer.name,
                        rating=rating,
                        body=text,
                        topic=case.kind,
                        source=conv.channel,
                    )
                )
            answers.append("Thank you. Your rating is saved with this case.")
            associated.append(case)
            continue
        if intent in KINDS and order:
            from app.domain.commerce import eligible
            from app.domain.common import policy as published_policy
            try:
                preflight_policy = published_policy(db, conv.merchant_id)
                eligible(order, intent, preflight_policy.rules)
                audit(db, conv.merchant_id, "coordinator", "tool.action_prerequisites_checked", conv.id,
                    input_message_id=message_id, requested_action=intent, order_id=order.id, passed=True)
            except HTTPException as exc:
                prior_intake = db.scalar(select(Case).where(Case.conversation_id == conv.id,
                    Case.order_id == order.id, Case.kind == intent, Case.primary_status != "resolved",
                    Case.proposal_ref.is_(None), Case.seller_approved.is_(False))
                    .order_by(Case.updated_at.desc()).limit(1).with_for_update())
                case = prior_intake or support_case(db, conv, intent + "_inquiry", fragment, order.id)
                if case.kind != intent + "_inquiry":
                    audit(db, conv.merchant_id, "coordinator", "case.reclassified", case.id,
                        input_message_id=message_id, previous_kind=case.kind, kind=intent + "_inquiry")
                    case.kind = intent + "_inquiry"
                case.details = {**case.details, "customer_claim": fragment,
                    "requested_resolution": intent, "missing_details": [],
                    "suggested_action": "Explain the failed prerequisites and discuss eligible alternatives.",
                    "verified_store_facts": {"order_id": order.id, "order_status": order.status,
                        "delivery_status": order.delivery_status}}
                transition(db, case, "flagged", "pending_verification", str(exc.detail))
                audit(db, conv.merchant_id, "coordinator", "tool.action_prerequisites_checked", case.id,
                    input_message_id=message_id, requested_action=intent, order_id=order.id, passed=False, reason=str(exc.detail))
                audit(db, conv.merchant_id, "coordinator", "case.escalated", case.id,
                    input_message_id=message_id, reason="action_prerequisites")
                associated.append(case)
                answers.append(f"I can't submit {intent} for {order.id}: {exc.detail} Case #{case.id[:6].upper()} is PENDING_VERIFICATION for the store to explain alternatives. No order change has been applied.")
                continue
        kind = issue.key if issue and intent == "support" else intent
        case = continuation or support_case(db, conv, kind, fragment, order.id if order else None)
        if not case.order_id and order:
            case.order_id = order.id
        associated.append(case)
        if issue:
            case.details = {**case.details, "issue_code": issue.code, "customer_issue": issue.name}
        msg.case_ids = list(set([*msg.case_ids, case.id]))
        current = db.scalar(
            select(Policy)
            .where(Policy.merchant_id == conv.merchant_id, Policy.published.is_(True))
            .order_by(Policy.version.desc())
            .limit(1)
        )
        evidence = list(db.scalars(select(Evidence).where(Evidence.case_id == case.id)))
        case.memory = {**case.memory, "context_refreshed_at": now().isoformat()}
        if intent == "support" or (intent == "complaint" and not order):
            from app.agents.public_answers import answer_support_question

            if issue and issue.review:
                flag(db, case, f"{issue.name}: seller must verify records and decide the next step.")
            else:
                transition(db, case, "ongoing", "needs_customer_details")
            facts = next_step(issue, conv.messaging_provider, bool(order)) if issue else (
                "Please share your order reference and describe what went wrong. "
                "The store must verify the order and issue before proposing a remedy."
            )
            if order:
                facts += f" Verified order reference: {order.id}."
            answer = answer_support_question(fragment, facts)
            outgoing = reply(db, conv, answer, cases=[case])
            audit_generated_reply(db, conv, outgoing, message_id)
        elif intent in KINDS or intent == "tracking" and not order:
            if order is None:
                transition(db, case, "ongoing", "needs_customer_details")
                answers.append(next_step(issue, conv.messaging_provider) if issue else "Please provide the order reference so we can verify the correct order.")
                continue
            # Refine extracted details against a freshly assembled, case-scoped context.
            if flow.get("refine"):
                from app.agents.router import refine_specialist

                state = {
                    "proposal": p,
                    "text": fragment,
                    "context": context_for(db, case, order, current, evidence),
                }
                p = refine_specialist(
                    state, "shopping" if intent in {"customization", "checkout"} else "resolution"
                )["proposal"]
            if case.status == "needs_details":
                case.details = {**case.details, "customer_clarification": fragment}
                flag(db, case, "Customer supplied the requested information; seller review is needed.")
            elif case.status not in {
                "pending_customer",
                "executing",
                "awaiting_return",
                "pickup_reserved",
                "pickup_ready",
            }:
                case = configure_request(db, case, conv, p)
            if case.status == "pending_customer":
                answers.append(confirmation_text(db, case))
            elif case.status == "needs_customer_details":
                answers.append(
                    "Please describe whether the item is damaged, defective or incorrect."
                    if intent in {"return", "refund", "replacement"}
                    else "Please provide the missing order or delivery details."
                )
            elif case.primary_status == "flagged":
                answers.append(f"Your {intent} request has been saved for store review. {case.flag_reason}")
            else:
                answers.append(
                    f"Your {intent} case is {case.status.replace('_', ' ')}. Its existing action is being tracked."
                )
        elif intent == "handoff":
            set_handoff(db, conv, True, "customer")
            answers.append(
                "I've transferred this conversation to the store team. Automated replies are paused."
            )
        elif intent == "unresolved":
            transition(db, case, "ongoing", "needs_customer_details")
            answers.append(issue.next_step if issue else "Please identify the unresolved request so the store can review its previous solution.")
        elif intent == "tracking" and order:
            answer = f"Order {order.id}: {order.delivery_status.replace('_', ' ')}. Order status: {order.status.replace('_', ' ')}."
            reply(db, conv, answer, cases=[case], completes=True)
            audit(db, conv.merchant_id, "support", "tracking.checked", case.id, order_id=order.id)
        elif intent in {"catalog", "policy"}:
            if intent == "policy" and not current:
                flag(db, case, "A published seller policy is missing.")
                answers.append("The store needs to clarify its policy before I can answer.")
            else:
                answer = (
                    f"The return window is {current.rules['return_window_days']} days after delivery for damaged, defective or incorrect items. Refunds follow inspection and the store's approval rules."
                    if intent == "policy"
                    else "Available products: "
                    + "; ".join(
                        f"{product.name}: {amount(product.price_paise)} ({product.stock - product.reserved_stock} available)"
                        for product in db.scalars(
                            select(Product).where(Product.merchant_id == conv.merchant_id)
                        )
                    )
                )
                from app.agents.public_answers import answer_public_question
                from app.core.config import get_settings
                import hashlib

                answer = answer_public_question(text, answer)
                outgoing = reply(db, conv, answer, cases=[case], completes=True)
                settings = get_settings()
                audit(db, conv.merchant_id, "support", "agent.reply_generated", outgoing.id,
                      input_message_id=message_id, ai_provider=settings.ai_mode,
                      model=settings.groq_model if settings.ai_mode == "groq" else "demo",
                      response_sha256=hashlib.sha256(answer.encode()).hexdigest())
        elif intent == "complaint" and order:
            transition(db, case, "ongoing", "needs_customer_details")
            answers.append(
                "Please send a clear product photo and describe the issue. The store will verify uncertain evidence."
            )
        else:
            flag(db, case, "The request needs clarification or a seller decision.")
            answers.append("I've saved this request for the store team to clarify.")
        audit(
            db,
            conv.merchant_id,
            "coordinator",
            "agent.proposed",
            case.id,
            intent=intent,
            message_id=message_id,
            elapsed_ms=round((monotonic() - started) * 1000),
        )
    if answers:
        reply(
            db, conv, "\n\n".join(answers), role="system" if conv.handoff else "assistant", cases=associated
        )
    msg.case_ids = list(dict.fromkeys([*msg.case_ids, *[c.id for c in associated]]))
    msg.processed = True
    db.flush()
    for case in associated:
        remember(db, case)
    return {"duplicate": False, "reply": "\n\n".join(answers) or "Saved reply", "case_ids": msg.case_ids}


def audit_generated_reply(db, conv, outgoing, message_id):
    import hashlib
    from app.core.config import get_settings

    settings = get_settings()
    audit(db, conv.merchant_id, "support", "agent.reply_generated", outgoing.id,
          input_message_id=message_id, ai_provider=settings.ai_mode,
          model=settings.groq_model if settings.ai_mode == "groq" else "demo",
          response_sha256=hashlib.sha256(outgoing.body.encode()).hexdigest())
