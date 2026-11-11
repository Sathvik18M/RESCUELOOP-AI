from pathlib import Path
from app.agents.specialists import assess_image
from app.db.models import Evidence
from app.integrations.storage import normalize_image, upload
from app.modules.common import audit, reply


def save_evidence(db, conv, raw: bytes, filename: str):
    content = normalize_image(raw)
    key = upload(conv.merchant_id, content)
    try:
        assessment = assess_image(content, "image/jpeg")
    except Exception:
        assessment = "Image stored. AI assessment is temporarily unavailable; seller review is required."
    evidence = Evidence(
        merchant_id=conv.merchant_id,
        conversation_id=conv.id,
        object_key=key,
        filename=Path(filename).name[:200],
        mime_type="image/jpeg",
        assessment=assessment,
    )
    db.add(evidence)
    db.flush()
    audit(db, conv.merchant_id, "vision", "evidence.saved", evidence.id)
    if not conv.handoff:
        reply(
            db,
            conv,
            "Your photo has been saved for review. You can request a return, replacement, refund, or warranty support.",
        )
    return evidence
