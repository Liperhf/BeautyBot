from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str
    ADMIN_TELEGRAM_ID: int

    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_NAME: str = "beauty_bot"
    DB_USER: str = "bot_user"
    DB_PASSWORD: str = "password"

    TIMEZONE: str = "Europe/Minsk"
    MORNING_REPORT_HOUR: int = 8
    REMINDER_24H: bool = True
    REMINDER_2H: bool = True

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()


def is_admin_user(user_id: int) -> bool:
    return True
