from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.adapters.live_market import fetch_etf_closes_daily
from app.config import get_backend_dir, get_settings

logger = logging.getLogger(__name__)

HV_CACHE_DIR = get_backend_dir() / "data" / "hv_cache"
HV_YEARS = 10
HV_WINDOW = 20
P_LOW, P_HIGH = 20, 80

MOCK_HV_PROFILES: dict[str, dict] = {
    "510050": {"hv20": 22.8, "vmin": 17.5, "vmax": 31.2},
    "510300": {"hv20": 21.5, "vmin": 18.0, "vmax": 32.0},
    "510500": {"hv20": 28.3, "vmin": 18.2, "vmax": 32.5},
}


@dataclass
class HvProfile:
    underlying: str
    hv20: float | None
    vmin: float
    vmax: float
    history_start: str | None
    history_end: str | None
    trading_days: int
    source: str
    computed_at: str


def rolling_hv20_series(closes: np.ndarray, window: int = HV_WINDOW) -> np.ndarray:
    if len(closes) < window + 1:
        return np.array([])
    log_ret = np.diff(np.log(closes))
    series = pd.Series(log_ret).rolling(window).std(ddof=1).dropna()
    return (series * np.sqrt(252) * 100).to_numpy(dtype=float)


def hv20_from_closes(closes: list[float]) -> float | None:
    if len(closes) < HV_WINDOW + 1:
        return None
    series = rolling_hv20_series(np.array(closes, dtype=float))
    return float(series[-1]) if len(series) else None


def iv_color_bands_from_closes(closes: list[float]) -> tuple[float, float] | None:
    series = rolling_hv20_series(np.array(closes, dtype=float))
    if len(series) < 60:
        return None
    p20, p80 = np.percentile(series, [P_LOW, P_HIGH])
    return float(p20), float(p80)


def _cache_path(underlying: str) -> Path:
    return HV_CACHE_DIR / f"{underlying}.json"


def _load_cache(underlying: str) -> HvProfile | None:
    path = _cache_path(underlying)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("computed_at") == date.today().isoformat():
            return HvProfile(**data)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("hv cache read failed %s: %s", underlying, exc)
    return None


def _save_cache(profile: HvProfile) -> None:
    HV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(profile.underlying).write_text(
        json.dumps(asdict(profile), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _mock_profile(underlying: str) -> HvProfile:
    mock = MOCK_HV_PROFILES.get(underlying, {"hv20": 22.0, "vmin": 18.0, "vmax": 32.0})
    end = date.today()
    start = end - timedelta(days=365 * HV_YEARS)
    return HvProfile(
        underlying=underlying,
        hv20=mock["hv20"],
        vmin=mock["vmin"],
        vmax=mock["vmax"],
        history_start=start.isoformat(),
        history_end=end.isoformat(),
        trading_days=252 * HV_YEARS,
        source="mock",
        computed_at=date.today().isoformat(),
    )


def _compute_live_profile(underlying: str) -> HvProfile:
    daily = fetch_etf_closes_daily(underlying, years=HV_YEARS)
    closes = [row["close"] for row in daily]
    dates = [row["date"] for row in daily]
    if len(closes) < HV_WINDOW + 60:
        logger.warning("insufficient history for %s (%s days), using mock", underlying, len(closes))
        profile = _mock_profile(underlying)
        return profile

    bands = iv_color_bands_from_closes(closes)
    hv20 = hv20_from_closes(closes)
    if not bands:
        profile = _mock_profile(underlying)
        return profile

    vmin, vmax = bands
    return HvProfile(
        underlying=underlying,
        hv20=hv20,
        vmin=vmin,
        vmax=vmax,
        history_start=dates[0] if dates else None,
        history_end=dates[-1] if dates else None,
        trading_days=len(closes),
        source="live",
        computed_at=date.today().isoformat(),
    )


def get_hv_profile(underlying: str) -> HvProfile:
    cached = _load_cache(underlying)
    if cached:
        return cached

    settings = get_settings()
    profile = _compute_live_profile(underlying) if settings.live_data else _mock_profile(underlying)
    _save_cache(profile)
    return profile


def get_underlying_hv_bands(underlying: str) -> tuple[float, float] | None:
    profile = get_hv_profile(underlying)
    return profile.vmin, profile.vmax
