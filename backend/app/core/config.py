from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # looks for .env in project root (parent of backend/) or in backend/ itself
    model_config = SettingsConfigDict(
        env_file=["../.env", ".env"],
        env_file_encoding="utf-8",
    )

    # Database
    database_url: str

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_jwt_secret: str

    # Pluggy
    pluggy_client_id: str
    pluggy_client_secret: str
    pluggy_base_url: str = "https://api.pluggy.ai"

    # Anthropic (opcional — substituído por OpenRouter)
    anthropic_api_key: str = ""

    # OpenRouter
    openrouter_key: str

    # App
    secret_key: str
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        # asyncpg requires postgresql+asyncpg:// scheme and ssl= instead of sslmode=
        v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        v = v.replace("sslmode=disable", "ssl=disable")
        return v


settings = Settings()
