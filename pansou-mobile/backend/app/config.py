from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "Pansou Mobile"
    debug: bool = False
    database_url: str = "mysql+pymysql://root:root@db:3306/pansou?charset=utf8mb4"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 120
    cors_origins: str = "*"
    admin_username: str = "admin"
    admin_password_hash: str = "$2b$12$2i0o4w1qgXyPfrv7ZW5s4uc.8pVbXtWpH2mOxj8q2sN.qEX2IuJeC"  # default: admin123
    page_size: int = 15

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
