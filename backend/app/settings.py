from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    version: str = "0.1.0"
    database_path: str = "/tmp/nomenclator.db"
    anthropic_api_key: str = "test"
    openai_api_key: str = ""
    auth_password_hash: str = ""
    monthly_spend_cap_usd: float = 20.0
    static_dir: str = "/app/static"
    debug: bool = False

    model_config = SettingsConfigDict(env_prefix="", env_file=".env")


settings = Settings()
