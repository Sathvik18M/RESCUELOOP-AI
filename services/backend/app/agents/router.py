import json
import re
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict
from openai import OpenAI
from app.core.config import get_settings


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Literal[
        "catalog",
        "tracking",
        "customization",
        "pickup",
        "redelivery",
        "refund",
        "return",
        "replacement",
        "cancellation",
        "warranty",
        "checkout",
        "handoff",
        "feedback",
        "complaint",
        "unknown",
    ]
    engraving: str | None
    gift_wrap: bool
    special_request: str | None
    address: str | None
    slot_id: Literal["SLOT-AM", "SLOT-PM"] | None
    amount_paise: int | None
    rating: int | None
    language: Literal["en", "kn"]


def classify(text: str, context: str):
    settings = get_settings()
    if settings.ai_mode == "demo":
        return demo_classify(text)
    schema = Proposal.model_json_schema()
    client = OpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=1)
    response = client.responses.create(
        model=settings.openai_model,
        store=False,
        instructions=(Path(__file__).parent / "prompts/conversation.txt").read_text(encoding="utf-8"),
        input=[{"role": "user", "content": f"Verified order context: {context}\nCustomer message: {text}"}],
        tools=[
            {
                "type": "function",
                "name": "propose_action",
                "description": "Propose an action for backend validation. This tool cannot execute it.",
                "parameters": schema,
                "strict": True,
            }
        ],
        tool_choice={"type": "function", "name": "propose_action"},
        parallel_tool_calls=False,
    )
    calls = [
        item for item in response.output if item.type == "function_call" and item.name == "propose_action"
    ]
    if len(calls) != 1:
        raise ValueError("No valid action proposal returned")
    return Proposal.model_validate(json.loads(calls[0].arguments)).model_dump()


def demo_classify(text: str):
    lower = text.lower()
    intent = "unknown"
    patterns = [
        ("handoff", r"human|owner|person|(?:talk|speak).*(?:seller)|ಮಾಲೀಕ"),
        ("feedback", r"[1-5]\s*(?:star|/5)"),
        ("customization", r"engrav|gift.?wrap|personal|custom|ಕೆತ್ತನೆ"),
        ("refund", r"refund|money back|ಮರುಪಾವತಿ"),
        ("return", r"return|ಹಿಂತಿರುಗ"),
        ("replacement", r"replace|exchange"),
        ("warranty", r"warranty|guarantee"),
        ("cancellation", r"cancel|ರದ್ದು"),
        ("pickup", r"pick.?up|collect|ಅಂಗಡಿ"),
        ("redelivery", r"redeliver|deliver again|address:"),
        ("complaint", r"damag|broken|wrong item|ಹಾನಿ"),
        ("tracking", r"where|track|delivery|late|ಎಲ್ಲಿ"),
        ("checkout", r"checkout|place.*order|buy|ಖರೀದಿ"),
        ("feedback", r"[1-5]\s*(?:star|/5)|review|feedback"),
        ("catalog", r"product|catalog|wallet|headphone|stock|price|ಬೆಲೆ"),
    ]
    for name, pattern in patterns:
        if re.search(pattern, lower):
            intent = name
            break
    name = re.search(r"engrav(?:e|ing)?\s+[\"']?([\w ]{1,40})", text, re.I)
    address = re.search(r"address:\s*(.+)", text, re.I)
    money = re.search(r"(?:₹|rs\.?\s*)(\d+(?:\.\d{1,2})?)", lower)
    rating = re.search(r"([1-5])\s*(?:star|/5)", lower)
    return Proposal(
        intent=intent,
        engraving=name.group(1).split(" and ")[0].strip()
        if name
        else ("Requested engraving" if "engrav" in lower else None),
        gift_wrap=bool(re.search(r"gift.?wrap", lower)),
        special_request=text if "custom" in lower else None,
        address=address.group(1) if address else None,
        slot_id="SLOT-AM" if "morning" in lower else "SLOT-PM" if "afternoon" in lower else None,
        amount_paise=round(float(money.group(1)) * 100) if money else None,
        rating=int(rating.group(1)) if rating else None,
        language="kn" if re.search(r"[\u0c80-\u0cff]", text) else "en",
    ).model_dump()


def refine_specialist(state, role: str):
    settings = get_settings()
    proposal = state["proposal"]
    if settings.ai_mode == "demo":
        return {"proposal": proposal, "specialist": role}
    client = OpenAI(api_key=settings.openai_api_key, timeout=30, max_retries=1)
    result = client.responses.parse(
        model=settings.openai_model,
        store=False,
        instructions=(Path(__file__).parent / f"prompts/{role}.txt").read_text(encoding="utf-8"),
        input=f"Proposal: {json.dumps(proposal)}\nContext: {state['context']}\nCustomer: {state['text']}",
        text_format=Proposal,
    )
    refined = result.output_parsed
    if refined is None or refined.intent != proposal["intent"]:
        raise ValueError("Specialist returned an inconsistent proposal")
    return {"proposal": refined.model_dump(), "specialist": role}


def localize_reply(text: str, language: str):
    settings = get_settings()
    if language != "kn" or settings.ai_mode != "openai":
        return text
    try:
        response = OpenAI(api_key=settings.openai_api_key, timeout=20, max_retries=1).responses.create(
            model=settings.openai_model,
            store=False,
            instructions="Translate the supplied customer-service reply into Kannada. Preserve every monetary amount, code, identifier, CONFIRM/DECLINE command and URL exactly. Do not add promises or facts. Return only the translated reply.",
            input=text,
        )
        translated = response.output_text
        protected = re.findall(
            r"₹[\d,.]+|\b(?:ORD\d+|CASE\d+|SLOT-[A-Z]+|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}|CONFIRM|DECLINE)\b",
            text,
        )
        return translated if translated and all(value in translated for value in protected) else text
    except Exception:
        return text
