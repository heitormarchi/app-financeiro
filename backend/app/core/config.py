from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=["../.env", ".env"],
        env_file_encoding="utf-8",
        extra="ignore",  # chaves antigas (supabase/pluggy) no .env não quebram
    )

    database_url: str
    app_api_key: str
    fernet_key: str  # gerar: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    openrouter_key: str
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_claims_email: str = "mailto:heitormarchicursos@gmail.com"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    evolution_base_url: str = ""
    evolution_api_key: str = ""
    evolution_instance: str = ""
    evolution_webhook_token: str = ""
    whatsapp_allowed_jid: str = ""
    inter_client_id: str = ""
    inter_client_secret: str = ""
    inter_cert_path: str = ""
    inter_key_path: str = ""
    inter_pix_dest_key: str = ""
    openrouter_vision_model: str = "google/gemini-2.0-flash-001"

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        v = v.replace("sslmode=disable", "ssl=disable")
        return v


settings = Settings()
