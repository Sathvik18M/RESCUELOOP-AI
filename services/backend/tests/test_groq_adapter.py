import json
import httpx
import pytest
from groq import Groq, RateLimitError
from pydantic import ValidationError
from app.agents import client as ai_client
from app.agents.specialists import PhotoAssessment
from app.core.config import get_settings
from app.domain.schemas import PolicyRules


def transport(monkeypatch, body, *, finish="stop", status=200, error_code="rate_limit_exceeded"):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_mode", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "test-groq-key")
    requests = []

    def respond(request):
        requests.append(request)
        data = (
            {"error": {"message": "Provider rejected output", "type": "invalid_request_error", "code": error_code}}
            if status != 200
            else {
                "id": "test-completion",
                "object": "chat.completion",
                "created": 1,
                "model": settings.groq_model,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": finish,
                        "message": {"role": "assistant", "content": json.dumps(body)},
                    }
                ],
            }
        )
        return httpx.Response(status, json=data, headers={"Retry-After": "15"})

    monkeypatch.setattr(
        ai_client,
        "Groq",
        lambda **kwargs: Groq(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond))),
    )
    return requests


def test_groq_text_uses_own_key_and_complete_strict_schema(monkeypatch):
    requests = transport(monkeypatch, PolicyRules().model_dump())
    result = ai_client.generate(PolicyRules, "Draft policy", "Synthetic request")
    assert result.return_window_days == 7
    request = requests[0]
    assert request.url.host == "api.groq.com"
    assert request.headers["authorization"] == "Bearer test-groq-key"
    payload = json.loads(request.content)
    schema = payload["response_format"]["json_schema"]
    assert schema["strict"] is True
    assert set(schema["schema"]["required"]) == set(schema["schema"]["properties"])
    assert schema["schema"]["additionalProperties"] is False


def test_groq_vision_rejects_invalid_assessment(monkeypatch):
    requests = transport(monkeypatch, {"quality": "approved", "observation": "A photo"})
    with pytest.raises(ValidationError):
        ai_client.generate(PhotoAssessment, "Observe only", "Synthetic photo", image=b"test")
    payload = json.loads(requests[0].content)
    assert payload["model"] == get_settings().groq_vision_model
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_photo_specialist_returns_validated_assessment(monkeypatch):
    from app.agents.specialists import assess_image

    transport(monkeypatch, {"quality": "unclear", "observation": "Product details cannot be distinguished."})
    result = assess_image(b"test", "image/jpeg")
    assert result["quality"] == "unclear"
    assert result["observation"]


def test_groq_truncated_result_is_not_accepted(monkeypatch):
    transport(monkeypatch, {"quality": "clear", "observation": "A photo"}, finish="length")
    with pytest.raises(ValueError, match="incomplete"):
        ai_client.generate(PhotoAssessment, "Observe only", "Synthetic photo")


def test_groq_rate_limit_is_left_to_durable_worker(monkeypatch):
    from app.workers.worker import delay_for, permanent

    requests = transport(monkeypatch, {}, status=429)
    with pytest.raises(RateLimitError) as error:
        ai_client.generate(PhotoAssessment, "Observe only", "Synthetic photo")
    assert len(requests) == 1
    assert delay_for(1, error.value) == 15
    assert not permanent(error.value)


def test_groq_invalid_generation_uses_durable_retry_budget(monkeypatch):
    from app.workers.worker import permanent

    requests = transport(monkeypatch, {}, status=400, error_code="json_validate_failed")
    with pytest.raises(ai_client.StructuredGenerationError) as error:
        ai_client.generate(PhotoAssessment, "Observe only", "Synthetic input")
    assert len(requests) == 1
    assert not permanent(error.value)
    assert "test-groq-key" not in str(error.value)


def test_groq_invalid_request_is_not_retried_as_generation(monkeypatch):
    from groq import BadRequestError
    from app.workers.worker import permanent

    requests = transport(monkeypatch, {}, status=400, error_code="invalid_request")
    with pytest.raises(BadRequestError) as error:
        ai_client.generate(PhotoAssessment, "Observe only", "Synthetic input")
    assert len(requests) == 1 and permanent(error.value)


def test_fractional_retry_after_is_respected():
    from app.workers.worker import delay_for

    response = httpx.Response(429, headers={"Retry-After": "27.5"}, request=httpx.Request("POST", "https://api.groq.com"))
    error = RateLimitError("Rate limited", response=response, body={})
    assert delay_for(1, error) == 28
