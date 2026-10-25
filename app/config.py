from urllib.parse import quote_plus
from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Теперь URL указывает на vkbottle_bot
    notification_service_url: str = "http://vkbottle_bot/api/v1/send-message"
    auth_token: str = ""  # Пока пустой, но готов к использованию

    timezone: str = "UTC"
    request_timeout: float = 10.0

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str
    postgres_db: str = "tasks_db"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @computed_field
    @property
    def database_url(self) -> str:
        pwd = quote_plus(self.postgres_password)
        return f"postgresql+psycopg://{self.postgres_user}:{pwd}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()