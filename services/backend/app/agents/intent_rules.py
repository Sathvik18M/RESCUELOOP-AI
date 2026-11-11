"""Explicit-language routing guards; model output cannot turn a status query into a dispute."""

import re


def split_requests(text):
    return [
        p.strip()
        for p in re.split(
            r"[;\n]+|\b(?:also|and)\s+(?=(?:please\s+)?(?:what|where|track|status|refund|return|engrave|customize|cancel|collect|pick up)\b)",
            text,
            flags=re.IGNORECASE,
        )
        if p.strip()
    ][:4]


def explicit_intent(text):
    lower = text.casefold().strip()
    if re.fullmatch(r"(?:hi|hello|hey|thanks|thank you)[.! ]*", lower):
        return "greeting"
    if re.search(r"\b(?:human|speak.*seller|talk.*seller)\b", lower):
        return "handoff"
    if re.search(r"\b(?:refund|payment|invoice)\b", lower):
        return None
    # A location/proof request is investigative, even without an explicit denial.
    if re.search(r"proof of delivery|where.*(?:was|got).*deliver|location.*deliver|deliver.*location", lower):
        return "delivery_dispute"
    if re.search(
        r"\b(?:not|never|haven't|haven’t|have not|didn't|didn’t|did not)\s+(?:yet\s+)?(?:received|receive|arrived|delivered)\b|not (?:yet )?delivered|hasn.t arrived|tracking.*wrong",
        lower,
    ):
        return "delivery_dispute"
    from app.agents.workflows.wrong_item import is_wrong_item

    if is_wrong_item(text):
        return "wrong_item"
    if re.search(r"customiz|customis|engrave|engraving|gift.?wrap", lower) and not re.search(
        r"wrong|missing|not included|wasn't included|wasn’t included|isn't ready|is not ready", lower
    ):
        return "customization"
    if re.search(
        r"\b(?:status|track|tracking)\b|where.*order|expected delivery date", lower
    ) and not re.search(r"refund|return|replacement|wrong|incorrect", lower):
        return "tracking"
    return None


def normalize(proposal):
    from app.domain.support_issues import BY_CODE

    item = dict(proposal)
    explicit = explicit_intent(item.get("request_text", ""))
    if explicit:
        item["intent"] = explicit
        item["issue_code"] = (
            "15"
            if explicit == "wrong_item"
            else "35"
            if explicit == "handoff"
            else "29"
            if explicit == "customization"
            else item.get("issue_code")
            if explicit == "delivery_dispute" and item.get("issue_code") in {"06", "09", "12"}
            else None
        )
    elif item.get("issue_code") in {"09", "12"}:
        item["intent"] = "delivery_dispute"
    elif item.get("issue_code") in BY_CODE:
        item["intent"] = BY_CODE[item["issue_code"]].intent
    item["requested_action"] = {
        "tracking": "ORDER_STATUS",
        "delivery_dispute": "DELIVERY_DISPUTE",
        "wrong_item": "WRONG_ITEM",
        "customization": "CUSTOMIZATION",
        "replacement": "REPLACEMENT",
        "return": "RETURN",
        "refund": "REFUND",
        "handoff": "HUMAN_ESCALATION",
    }.get(item["intent"], item["intent"].upper())
    return item
