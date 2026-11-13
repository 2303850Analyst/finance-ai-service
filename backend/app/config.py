from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Finance AI Service"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/finance_ai"

    # ── AI Provider ────────────────────────────────────────────────────────────
    # Values: "mock" | "openrouter"
    ai_provider: str = "mock"
    ai_ca_file: str | None = None

    # OpenRouter — key stored as SecretStr so it never appears in repr/logs
    openrouter_api_key: SecretStr | None = None
    openrouter_model_primary: str = "deepseek/deepseek-v3.2"
    openrouter_model_fallback: str = "deepseek/deepseek-chat"

    # ── AI Behaviour ───────────────────────────────────────────────────────────
    ai_max_input_chars: int = 2000
    ai_max_output_tokens: int = 500
    ai_temperature: float = 0.0

    # ── AI Rate Limits ─────────────────────────────────────────────────────────
    ai_daily_request_limit: int = 20
    ai_monthly_request_limit: int = 200
    ai_cooldown_seconds: int = 5
    ai_monthly_budget_usd: float = 10.0
    ai_user_monthly_budget_usd: float = 0.25

    telegram_bot_token: SecretStr | None = None
    telegram_internal_secret: SecretStr | None = None
    telegram_bot_username: str = "FinAI_sychikoff_bot"
    backend_internal_url: str = "http://backend:8000"
    transcription_model: str = "openai/whisper-1"
    miniapp_auth_max_age_seconds: int = 3600
    miniapp_url: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
