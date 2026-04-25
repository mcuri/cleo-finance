from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_client_id: str
    google_client_secret: str
    google_sheets_id: str
    session_secret: str
    allowed_email: str
    telegram_bot_token: str
    telegram_webhook_secret: str
    anthropic_api_key: str
    app_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:5173"
    google_service_account_json: str = ""

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
