from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Finance AI Service"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/finance_ai"

    model_config = {"env_file": ".env"}


settings = Settings()
