from __future__ import annotations

import json

from app.config import get_backend_dir, get_settings
from app.models.schemas import SettingsModel

SETTINGS_PATH = get_backend_dir() / "data" / "settings.json"


def load_settings() -> SettingsModel:
    cfg = get_settings()
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return SettingsModel(**data)
        except (json.JSONDecodeError, ValueError):
            pass
    return SettingsModel(
        r=cfg.default_risk_free_rate,
        q=cfg.default_dividend_yield,
        quote_refresh_sec=cfg.quote_refresh_sec,
        home_refresh_sec=cfg.home_refresh_sec,
    )


def save_settings(model: SettingsModel) -> SettingsModel:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    return model
