from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "PanSou Python"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "sqlite:///./pansou.db"

    upstream_pansou_enabled: bool = True
    upstream_pansou_base_url: str = "https://so.252035.xyz"
    upstream_pansou_timeout: float = 8.0

    native_plugins_enabled: bool = True

    cache_ttl: int = 300
    plugin_timeout: float = 3.0
    search_timeout: float = 6.0
    max_concurrent_plugins: int = 8

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
