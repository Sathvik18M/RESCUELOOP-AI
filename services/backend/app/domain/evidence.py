from pathlib import Path
from sqlalchemy import select
from app.agents.specialists import assess_image
from app.persistence.models import Evidence, Case
from app.integrations.storage import normalize_image, upload
from app.domain.common import audit, reply
from app.domain.cases import flag, support_case
from app.domain.support_issues import BY_CODE, EVIDENCE_ISSUES


def save_evidence(db, conv, raw, filename, case_id=None):
    if case_id:
        case = db.scalar(select(Case).where(Case.id == case_id, Case.conversation_id == conv.id))
    else:
        candidates = list(
            db.scalars(
                select(Case).where(
                    Case.conversation_id == conv.id,
                    Case.primary_status != "resolved",
                    Case.kind.in_([
                        "return", "refund", "replacement", "complaint", "customization",
                        *[BY_CODE[code].key for code in EVIDENCE_ISSUES],
                    ]),
                )
            )
        )
        case = candidates[0] if len(candidates) == 1 else None
    ambiguous = case is None
    if not case:
        case = support_case(db, conv, "complaint", "Product photo needs case clarification", order_id=None)
    content = normalize_image(raw)
    observation = assess_image(content, "image/jpeg")
    key = upload(conv.merchant_id, content)
    item = Evidence(
        merchant_id=conv.merchant_id,
        conversation_id=conv.id,
        case_id=case.id,
        object_key=key,
        filename=Path(filename).name[:200],
        mime_type="image/jpeg",
        assessment=observation["observation"],
        quality=observation["quality"],
    )
    db.add(item)
    db.flush()
    audit(
        db,
        conv.merchant_id,
        "photo-specialist",
        "evidence.saved",
        case.id,
        evidence_id=item.id,
        quality=item.quality,
    )
    if ambiguous:
        flag(
            db,
            case,
            "Photo could not be matched to one open request. Confirm the order and case before using it.",
        )
        text = "Your photo is saved. Please tell the store which order and request it belongs to."
    elif item.quality != "clear":
        flag(db, case, "Product photo is unclear or unassessed. Manual verification is required.")
        text = "Your photo is saved with this case for store verification."
    else:
        from app.domain.commerce import configure_request, confirmation_text

        if (
            case.kind in {"return", "refund", "replacement"}
            and not conv.handoff
            and case.status in {"pending_seller", "needs_customer_details", "investigating"}
        ):
            configure_request(db, case, conv, {})
        text = (
            confirmation_text(db, case)
            if case.status == "pending_customer"
            else "Your clear photo is saved. Eligibility and approval are checked separately."
        )
    if not conv.handoff:
        reply(db, conv, text, cases=[case])
    return item
