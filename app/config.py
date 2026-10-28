from dotenv import load_dotenv
from urllib.parse import quote
from pydantic import computed_field
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    # Теперь URL указывает на vkbottle_bot
    notification_service_url: str = "http://vkbottle_bot/api/v1/send-message"
    auth_token: str = ""  # Пока пустой, но готов к использованию

    timezone: str = "UTC"
    request_timeout: float = 10.0

    max_delivery_attempts: int = 5
    retry_base_delay: int = 30  # секунд, удваивается с каждой попыткой
    stale_after_seconds: int = 900  # не слать напоминание, если событие началось раньше

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str
    postgres_db: str = "tasks_db"

    @computed_field
    @property
    def database_url(self) -> str:
        pwd = quote(self.postgres_password, safe="")
        return f"postgresql+psycopg://{self.postgres_user}:{pwd}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()