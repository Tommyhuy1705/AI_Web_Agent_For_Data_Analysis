"""
Core Configuration — SIA Backend
Centralized settings management using pydantic-settings.
All environment variables are parsed and validated here.
"""
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str = "SIA — Sales Intelligence Agent"
    app_version: str = "1.0.0"
    debug: bool = False
    frontend_url: str = "http://localhost:3000"

    # ── Supabase ─────────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    supabase_database_url: str = ""
    supabase_db_host: str = ""
    supabase_db_port: int = 5432
    supabase_db_user: str = ""
    supabase_db_password: str = ""
    supabase_db_name: str = "postgres"

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_provider: str = "openai"          # "openai" | "qwen"
    openai_api_key: str = ""
    dashscope_api_key: str = ""           # Qwen / Alibaba DashScope

    # ── Dify ─────────────────────────────────────────────────────────────────
    dify_api_url: str = ""
    dify_api_key: str = ""

    # ── SendGrid ─────────────────────────────────────────────────────────────
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = ""
    alarm_recipient_emails: str = ""      # Comma-separated list

    # ── TinyFish ─────────────────────────────────────────────────────────────
    tinyfish_api_key: str = ""

    # ── Zilliz ───────────────────────────────────────────────────────────────
    zilliz_uri: str = ""
    zilliz_token: str = ""

    # ── AWS (for deployment metadata) ────────────────────────────────────────
    aws_region: str = "ap-southeast-1"
    ecr_registry: str = ""

    @property
    def alarm_emails(self) -> list[str]:
        """Parse comma-separated alarm recipient emails."""
        return [e.strip() for e in self.alarm_recipient_emails.split(",") if e.strip()]

    @property
    def is_tinyfish_configured(self) -> bool:
        return bool(self.tinyfish_api_key)

    @property
    def is_dify_configured(self) -> bool:
        return bool(self.dify_api_url and self.dify_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance (singleton pattern)."""
    return Settings()
