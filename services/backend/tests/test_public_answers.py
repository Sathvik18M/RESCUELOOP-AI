import pytest

from app.agents import public_answers
from app.core.config import get_settings

FACTS = (
    "The return window is 7 days after delivery for damaged, defective or incorrect items. "
    "Refunds follow inspection and the store's approval rules."
)


def generated_answer(monkeypatch, answer):
    monkeypatch.setattr(get_settings(), "ai_mode", "groq")
    monkeypatch.setattr(public_answers, "generate", lambda *a, **kw: public_answers.PublicAnswer(answer=answer))


def test_grounded_policy_requirements_are_allowed(monkeypatch):
    answer = (
        "You can request a return within 7 days after delivery for damaged, defective or incorrect items. "
        "Refunds require inspection and store approval."
    )
    generated_answer(monkeypatch, answer)
    assert public_answers.answer_public_question("What is your return policy now?", FACTS) == answer


@pytest.mark.parametrize("answer", [
    "Your refund is approved.",
    "Your return has been initiated.",
    "Refunds will be processed after an inspection and approval according to our standard rules.",
    "You can return any item within 30 days.",
    "Visit https://example.test/refund to get your refund.",
])
def test_unsafe_or_unsupported_public_reply_remains_blocked(monkeypatch, answer):
    generated_answer(monkeypatch, answer)
    with pytest.raises(ValueError):
        public_answers.answer_public_question("What is your return policy now?", FACTS)
