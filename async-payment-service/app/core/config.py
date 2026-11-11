from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "async-payment-service"
    api_key: str = "dev-secret-change-me"
    database_url: str = "postgresql+asyncpg://payments:payments@localhost:5432/payments"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    outbox_poll_interval: float = 1.0
    webhook_timeout: float = 5.0

settings = Settings()
