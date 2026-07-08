from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "PanSou Python"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "sqlite:///./pansou.db"

    upstream_pansou_enabled: bool = True
    upstream_pansou_base_url: str = "http://127.0.0.1:8888"
    upstream_pansou_timeout: float = 5.0

    native_plugins_enabled: bool = False

    cache_ttl: int = 3600
    plugin_timeout: float = 5.0
    search_timeout: float = 8.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
