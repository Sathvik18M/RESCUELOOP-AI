"""Hosted demos retain real authentication and fail if either process exits."""

import pytest
from app.core.config import Settings
from app import hosted


def hosted_settings(**changes):
    values = dict(
        _env_file=None, app_env="staging", demo_mode=False, ai_mode="groq",
        groq_api_key="test-only", supabase_url="https://example.invalid",
        supabase_service_role_key="test-only", public_webhook_url="https://demo.invalid",
        database_url="postgresql://test:test@db.invalid/postgres?sslmode=require",
        whatsapp_provider="360dialog_sandbox", d360_api_key="test-only",
        d360_sandbox_recipient="test-recipient", d360_webhook_secret="x" * 40,
    )
    values.update(changes)
    return Settings(**values)


def test_staging_supports_sandbox_with_real_authentication():
    settings = hosted_settings()
    settings.validate_runtime()
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.database_url.endswith("?sslmode=require")
    with pytest.raises(ValueError):
        hosted_settings(demo_mode=True).validate_runtime()
    with pytest.raises(ValueError):
        hosted_settings(ai_mode="demo").validate_runtime()
    with pytest.raises(ValueError):
        hosted_settings(supabase_service_role_key="").validate_runtime()
    with pytest.raises(ValueError):
        hosted_settings(app_env="production").validate_runtime()


@pytest.mark.parametrize("failed_child", [0, 1])
def test_supervisor_stops_other_process_when_api_or_worker_exits(monkeypatch, failed_child):
    class Child:
        def __init__(self, code):
            self.code = code
            self.terminated = False

        def poll(self):
            return self.code

        def terminate(self):
            self.terminated = True
            self.code = -15

        def wait(self, timeout=None):
            return self.code

    children = [Child(None), Child(None)]
    children[failed_child].code = 1
    iterator = iter(children)
    monkeypatch.setattr(hosted.subprocess, "Popen", lambda command: next(iterator))
    assert hosted.supervise([["api"], ["worker"]]) == 1
    assert children[1 - failed_child].terminated
