"""Groq structured generation. Model output never authorizes business operations."""

import base64
import json
from typing import TypeVar
from groq import BadRequestError, Groq
from pydantic import BaseModel
from app.core.config import get_settings

Result = TypeVar("Result", bound=BaseModel)


class StructuredGenerationError(ValueError):
    """Retryable model-output validation failure; contains no raw prompt or provider body."""


def provider_error_code(exc):
    body = getattr(exc, "body", None)
    error = body.get("error", body) if isinstance(body, dict) else {}
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, str) and code.replace("_", "").isalnum() and len(code) < 80 else None


def strict_schema(model: type[BaseModel]):
    schema = model.model_json_schema()

    def visit(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object" or "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(schema)
    return schema


def generate(
    model: type[Result],
    instructions: str,
    text: str,
    *,
    image: bytes | None = None,
    mime_type: str = "image/jpeg",
) -> Result:
    settings = get_settings()
    if settings.ai_mode != "groq" or not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY and AI_MODE=groq are required for live generation")
    content = text
    if image is not None:
        # Groq's vision interface documents JSON object mode. Validate its output locally.
        instructions += "\nReturn only a JSON object matching this schema: " + json.dumps(
            strict_schema(model)
        )
        content = [
            {"type": "text", "text": text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{base64.b64encode(image).decode()}"},
            },
        ]
    with Groq(api_key=settings.groq_api_key, timeout=settings.model_timeout_seconds, max_retries=0) as client:
        try:
            response = client.chat.completions.create(
                model=settings.groq_vision_model if image is not None else settings.groq_model,
                messages=[{"role": "system", "content": instructions}, {"role": "user", "content": content}],
                response_format={"type": "json_object"}
                if image is not None
                else {
                    "type": "json_schema",
                    "json_schema": {"name": model.__name__, "strict": True, "schema": strict_schema(model)},
                },
                max_completion_tokens=4096,
                stream=False,
            )
        except BadRequestError as exc:
            # Only model-output failures are safe to regenerate. Invalid requests/credentials
            # remain permanent; the durable worker owns the existing three-attempt budget.
            if provider_error_code(exc) in {"json_validate_failed", "json_schema_validation_failed"}:
                raise StructuredGenerationError("Groq structured output validation failed") from exc
            raise
    if not response.choices or response.choices[0].finish_reason != "stop":
        raise ValueError("AI response was refused or incomplete")
    body = response.choices[0].message.content
    if not body:
        raise ValueError("AI response did not contain a structured result")
    return model.model_validate_json(body)
