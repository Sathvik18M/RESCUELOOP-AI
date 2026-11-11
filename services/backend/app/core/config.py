from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator

ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    app_env: str = "development"
    local_verification_only: bool = False
    demo_mode: bool = True
    demo_token: str = "local-rescueloop-demo"
    database_url: str = "postgresql+psycopg://rescueloop:rescueloop@127.0.0.1:5432/rescueloop_rebuild"
    cors_origins: str = "http://localhost:3100,http://127.0.0.1:3100"
    ai_mode: str = "demo"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_vision_model: str = "qwen/qwen3.8-27b"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "evidence"
    seller_user_id: str = ""
    whatsapp_provider: str = "disabled"
    whatsapp_merchant_id: str = "SELLER001"
    d360_api_key: str = ""
    d360_sandbox_recipient: str = ""
    d360_recipient_type: str = "phone"
    d360_webhook_secret: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = ""
    twilio_merchant_id: str = "SELLER001"
    public_webhook_url: str = ""
    model_timeout_seconds: int = 45
    evidence_root: str = ".local/rebuild-evidence"

    @field_validator("database_url")
    @classmethod
    def postgres_driver(cls, value):
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @model_validator(mode="after")
    def isolate_local_verification(self):
        if self.local_verification_only:
            self.app_env = "development"
            self.demo_mode = True
            self.ai_mode = "demo"
            self.demo_token = "local-rescueloop-demo"
            self.whatsapp_provider = "disabled"
            self.database_url = "postgresql+psycopg://rescueloop:rescueloop@127.0.0.1:5432/rescueloop_rebuild"
            self.cors_origins = "http://localhost:3100,http://127.0.0.1:3100"
            self.evidence_root = ".local/rebuild-evidence"
            for key in [
                "groq_api_key",
                "supabase_url",
                "supabase_service_role_key",
                "twilio_account_sid",
                "twilio_auth_token",
                "twilio_whatsapp_from",
                "public_webhook_url",
                "d360_api_key",
                "d360_sandbox_recipient",
                "d360_webhook_secret",
            ]:
                setattr(self, key, "")
        return self

    def validate_runtime(self):
        if self.whatsapp_provider not in {"disabled", "twilio", "360dialog_sandbox"}:
            raise ValueError("Unknown WHATSAPP_PROVIDER")
        if self.d360_recipient_type not in {"phone", "bsuid"}:
            raise ValueError("D360_RECIPIENT_TYPE must be phone or bsuid")
        if self.app_env in {"staging", "production"}:
            if self.demo_mode or self.ai_mode != "groq":
                raise ValueError("Hosted environments require DEMO_MODE=false and AI_MODE=groq")
            required = [
                self.supabase_url,
                self.supabase_service_role_key,
                self.groq_api_key,
                self.public_webhook_url,
            ]
            from app.integrations.whatsapp import is_configured

            if self.app_env == "production" and self.whatsapp_provider == "360dialog_sandbox":
                raise ValueError("360dialog Sandbox requires development or staging")
            if not is_configured(self):
                raise ValueError("Hosted environments require an active configured WhatsApp provider")
            if not all(required) or not self.database_url.startswith("postgresql"):
                raise ValueError("Hosted environments require PostgreSQL, Supabase, Groq, and WhatsApp configuration")
        if self.ai_mode not in {"demo", "groq"}:
            raise ValueError("AI_MODE must be demo or groq")
        if self.ai_mode == "groq" and not self.groq_api_key:
            raise ValueError("GROQ_API_KEY is required for AI_MODE=groq")


@lru_cache
def get_settings():
    return Settings()
