"""
Core Configuration — SIA Backend
Centralized settings management using pydantic-settings.
All environment variables are parsed and validated here.

Active integrations:
- Supabase (PostgreSQL analytics DB)
- DashScope/Qwen (Primary LLM)
- OpenAI (Fallback LLM)
- TinyFish (Quantitative market crawl)
- Exa (Qualitative market news search)
- ElevenLabs (Text-to-Speech audio briefing)
- SendGrid (Alarm email notifications)
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

    # ── LLM — DashScope/Qwen (primary) → OpenAI (fallback) ──────────────────
    llm_provider: str = "openai"            # "openai" | "qwen"
    openai_api_key: str = ""
    dashscope_api_key: str = ""             # Qwen / Alibaba DashScope
    dashscope_model: str = "qwen3.5-122b-a10b"

    # ── SendGrid (Alarm Email) ────────────────────────────────────────────────
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = ""
    alert_recipients: str = ""              # Comma-separated list

    # ── TinyFish (Quantitative Market Crawl) ─────────────────────────────────
    tinyfish_api_key: str = ""

    # ── Exa (Qualitative Market News Search) ─────────────────────────────────
    exa_api_key: str = ""

    # ── ElevenLabs (Text-to-Speech Audio Briefing) ───────────────────────────
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"   # Default: Rachel (EN)
    elevenlabs_model_id: str = "eleven_multilingual_v2"

    # ── AWS (deployment metadata) ─────────────────────────────────────────────
    aws_region: str = "ap-southeast-1"
    ecr_registry: str = ""

    # ── Computed properties ───────────────────────────────────────────────────
    @property
    def alarm_emails(self) -> list[str]:
        """Parse comma-separated alarm recipient emails."""
        return [e.strip() for e in self.alert_recipients.split(",") if e.strip()]

    @property
    def is_tinyfish_configured(self) -> bool:
        return bool(self.tinyfish_api_key)

    @property
    def is_exa_configured(self) -> bool:
        return bool(self.exa_api_key)

    @property
    def is_elevenlabs_configured(self) -> bool:
        return bool(self.elevenlabs_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance (singleton pattern)."""
    return Settings()
