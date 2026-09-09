from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# Portable: paths are always relative to this backend folder, never a fixed drive letter.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ENV_FILE = _BACKEND_DIR / ".env"
_DATA_DIR = _BACKEND_DIR / "data"


def get_backend_dir() -> Path:
    return _BACKEND_DIR


def resolve_data_path(*parts: str) -> Path:
    return (_DATA_DIR.joinpath(*parts)).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ETF Option Assistant"
    debug: bool = True
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    data_source: str = "eastmoney"
    sina_auxiliary: bool = False

    default_risk_free_rate: float = 0.02
    default_dividend_yield: float = 0.0
    quote_refresh_sec: int = 8
    home_refresh_sec: int = 30
    live_data: bool = False  # True 时尝试 AKShare 拉实时行情（可能较慢）

    database_url: str = "sqlite:///./data/app.db"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_env_diagnostics() -> dict:
    """Help debug why LIVE_DATA may not load from .env."""
    import os

    settings = get_settings()
    return {
        "env_file": str(_ENV_FILE),
        "env_file_exists": _ENV_FILE.exists(),
        "cwd": str(Path.cwd()),
        "live_data_from_settings": settings.live_data,
        "live_data_env_var": os.environ.get("LIVE_DATA"),
        "sina_auxiliary_env_var": os.environ.get("SINA_AUXILIARY"),
    }
