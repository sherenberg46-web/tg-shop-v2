from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DB_PATH: str = "database/shop.db"

    # Telegram
    BOT_TOKEN: str = ""
    WEBAPP_URL: str = "https://sublime-serenity-production-dde7.up.railway.app"
    ADMIN_ID: int = 0
    MANAGER_CHAT_ID: int = 0  # extra recipient for order notifications (e.g. @gamestore_by)
    # Full URL to THIS backend, used to register the Telegram webhook
    # e.g. https://tg-shop-production-1b03.up.railway.app
    WEBHOOK_HOST: str = ""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # CORS – comma-separated origins, use * to allow all (needed for Telegram Mini App)
    CORS_ORIGINS: str = "*"

    # Admin panel password
    ADMIN_PASSWORD: str = "admin1234"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


settings = Settings()
