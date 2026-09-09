from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from app.config import get_settings
from app.infra.cache import market_cache

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=8)


def _fetch_one(code: str) -> tuple[str, float | None, float | None]:
    import akshare as ak

    try:
        df = ak.option_sse_spot_price_sina(symbol=code)
        field_map = dict(zip(df["字段"].astype(str), df["值"].astype(str), strict=False))
        bid = _parse_price(field_map.get("申买价一") or field_map.get("买价"))
        ask = _parse_price(field_map.get("申卖价一") or field_map.get("卖价"))
        return code, bid, ask
    except Exception as exc:
        logger.debug("sina quote %s failed: %s", code, exc)
        return code, None, None


def _parse_price(raw: str | None) -> float | None:
    if raw is None or raw in ("", "-", "0", "0.0"):
        return None
    try:
        val = float(raw)
        return val if val > 0 else None
    except ValueError:
        return None


def _cached_fetch(code: str) -> tuple[str, float | None, float | None]:
    return market_cache.get_or_set(
        f"sina_bid_ask_{code}",
        ttl_sec=10,
        factory=lambda: _fetch_one(code),
    )


def fetch_bid_ask_batch(codes: list[str], timeout: float = 12.0) -> dict[str, tuple[float | None, float | None]]:
    settings = get_settings()
    if not settings.sina_auxiliary or not codes:
        return {}

    unique = list(dict.fromkeys(codes))
    result: dict[str, tuple[float | None, float | None]] = {}
    futures = [_executor.submit(_cached_fetch, code) for code in unique]
    for fut in futures:
        try:
            code, bid, ask = fut.result(timeout=timeout)
            if bid or ask:
                result[code] = (bid, ask)
        except Exception as exc:
            logger.debug("sina batch timeout/error: %s", exc)
    return result
