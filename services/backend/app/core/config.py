from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    app_env: str = "development"
    demo_mode: bool = True
    demo_token: str = "local-rescueloop-demo"
    database_url: str = "postgresql+psycopg://rescueloop:rescueloop@127.0.0.1:5432/rescueloop"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    ai_mode: str = "demo"
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "evidence"
    seller_user_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_graph_version: str = "v23.0"
    whatsapp_update_template: str = ""

    def validate_runtime(self):
        if self.app_env == "production":
            if self.demo_mode or self.ai_mode != "openai":
                raise ValueError("Production requires DEMO_MODE=false and AI_MODE=openai")
            required = [
                self.supabase_url,
                self.supabase_service_role_key,
                self.openai_api_key,
                self.whatsapp_app_secret,
                self.whatsapp_access_token,
                self.whatsapp_phone_number_id,
                self.whatsapp_verify_token,
            ]
            if not all(required) or not self.database_url.startswith("postgresql"):
                raise ValueError(
                    "Production requires PostgreSQL, Supabase, OpenAI, and WhatsApp configuration"
                )
        if self.ai_mode not in {"demo", "openai"}:
            raise ValueError("AI_MODE must be demo or openai")
        if self.ai_mode == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for AI_MODE=openai")


@lru_cache
def get_settings():
    return Settings()
