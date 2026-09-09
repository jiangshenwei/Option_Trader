from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout, as_completed
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

from app.infra.cache import market_cache

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)

ETF_CODES = ("510050", "510300", "510500")

_last_chain_fetch: datetime | None = None
_last_chain_source: str = "mock"
_last_chain_error: str | None = None


def get_market_status() -> dict[str, Any]:
    return {
        "chain_source": _last_chain_source,
        "chain_updated_at": _last_chain_fetch.isoformat() if _last_chain_fetch else None,
        "chain_error": _last_chain_error,
    }


def _fetch_option_current_em() -> pd.DataFrame:
    import akshare as ak

    return ak.option_current_em()


def _fetch_etf_spot() -> pd.DataFrame:
    import akshare as ak

    return ak.fund_etf_spot_em()


def _fetch_etf_hist(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    import akshare as ak

    return ak.fund_etf_hist_em(
        symbol=code,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="",
    )


def fetch_option_chain_df(
    timeout: float = 25.0,
    retries: int = 2,
    *,
    underlying: str | None = None,
    spot: float | None = None,
    listed_months: list[dict] | None = None,
    strike_min: float | None = None,
    strike_max: float | None = None,
    otm_only: bool = False,
    include_non_standard: bool = False,
) -> pd.DataFrame | None:
    global _last_chain_fetch, _last_chain_source, _last_chain_error

    scoped = underlying is not None and spot is not None and listed_months is not None
    if scoped:
        cache_key = (
            f"option_chain_sina_{underlying}_{int(include_non_standard)}_{int(otm_only)}"
            f"_{strike_min}_{strike_max}"
        )
    else:
        cache_key = f"option_chain_sina_{'full' if include_non_standard else 'std'}"

    def _load_em() -> pd.DataFrame:
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return _executor.submit(_fetch_option_current_em).result(timeout=timeout)
            except Exception as exc:
                last_exc = exc
                if attempt < retries:
                    logger.info("option_current_em retry %s/%s", attempt + 1, retries)
        raise last_exc or RuntimeError("option_current_em failed")

    def _load_sina() -> pd.DataFrame:
        from app.adapters.sina_chain import build_option_chain_df

        return build_option_chain_df(
            timeout=timeout,
            underlying=underlying,
            spot=spot,
            listed_months=listed_months,
            strike_min=strike_min,
            strike_max=strike_max,
            otm_only=otm_only,
            include_non_standard=include_non_standard,
        )

    def _try_source(
        key: str,
        loader,
        factory_timeout: float,
    ) -> pd.DataFrame | None:
        try:
            df = market_cache.get_or_set(
                key,
                ttl_sec=30,
                factory=lambda: _executor.submit(loader).result(timeout=factory_timeout),
            )
            if df is not None and not df.empty:
                return df
        except FuturesTimeout:
            logger.warning("%s option chain timeout", key)
        except Exception as exc:
            logger.warning("%s option chain failed: %s", key, exc)
        return None

    # Sina first — EastMoney often fails on this network; cached hits are instant.
    sina_df = _try_source(cache_key, _load_sina, timeout + 10)
    if sina_df is not None:
        _last_chain_fetch = datetime.now()
        _last_chain_source = "sina"
        _last_chain_error = None
        return sina_df

    if scoped:
        return None

    em_df = _try_source("option_chain_em", _load_em, timeout + 5)
    if em_df is not None:
        _last_chain_fetch = datetime.now()
        _last_chain_source = "eastmoney"
        _last_chain_error = None
        return em_df

    _last_chain_source = "mock"
    _last_chain_error = "option chain unavailable (sina and eastmoney failed)"
    logger.warning(_last_chain_error)
    return None


def fetch_etf_spots(timeout: float = 5.0) -> dict[str, dict]:
    """Return spot/chg/source per ETF code. Tries EastMoney, then Sina per missing code."""

    def _load_em() -> dict[str, dict]:
        df = _fetch_etf_spot()
        out: dict[str, dict] = {}
        for code in ETF_CODES:
            row = df[df["代码"] == code]
            if row.empty:
                continue
            spot = float(row.iloc[0]["最新价"])
            chg = float(row.iloc[0].get("涨跌幅", 0) or 0)
            out[code] = {"spot": spot, "chg": chg, "source": "eastmoney"}
        return out

    def _load_sina(code: str) -> dict | None:
        import akshare as ak

        symbol = f"sh{code}"
        try:
            df = ak.option_sse_underlying_spot_price_sina(symbol=symbol)
            field_map = dict(zip(df["字段"].astype(str), df["值"].astype(str), strict=False))
            spot = _parse_price(field_map.get("最近成交价"))
            prev = _parse_price(field_map.get("昨日收盘价"))
            if not spot:
                return None
            chg = ((spot / prev) - 1) * 100 if prev else 0.0
            return {"spot": spot, "chg": chg, "source": "sina"}
        except Exception as exc:
            logger.debug("sina spot %s failed: %s", code, exc)
            return None

    result: dict[str, dict] = {}
    try:
        result = market_cache.get_or_set(
            "etf_spot_bundle",
            ttl_sec=15,
            factory=lambda: _executor.submit(_load_em).result(timeout=timeout),
        )
    except Exception as exc:
        logger.warning("fund_etf_spot_em failed: %s", exc)

    missing = [code for code in ETF_CODES if code not in result]
    if missing:
        futures = {_executor.submit(_load_sina, code): code for code in missing}
        try:
            for fut in as_completed(futures, timeout=6.0):
                code = futures[fut]
                try:
                    sina = fut.result()
                    if sina:
                        result[code] = sina
                except Exception as exc:
                    logger.debug("sina spot %s failed: %s", code, exc)
        except FuturesTimeout:
            logger.debug("sina spot batch timeout")

    return result


def _parse_price(raw: str | float | None) -> float | None:
    if raw is None:
        return None
    try:
        val = float(str(raw).strip().replace(",", ""))
        return val if val > 0 else None
    except ValueError:
        return None


def fetch_etf_closes_daily(code: str, years: int = 10, timeout: float = 20.0) -> list[dict]:
    end = date.today()
    start = end - timedelta(days=365 * years)

    def _load() -> list[dict]:
        df = _fetch_etf_hist(code, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        if df is None or df.empty:
            return []
        return [
            {
                "date": str(r["日期"])[:10],
                "open": float(r["开盘"]),
                "high": float(r["最高"]),
                "low": float(r["最低"]),
                "close": float(r["收盘"]),
            }
            for _, r in df.iterrows()
        ]

    try:
        return market_cache.get_or_set(
            f"etf_hist_long_{code}_{years}y",
            ttl_sec=86400,
            factory=lambda: _executor.submit(_load).result(timeout=timeout),
        )
    except Exception as exc:
        logger.warning("fund_etf_hist_em long %s failed: %s", code, exc)
        return []


def fetch_etf_ohlc(code: str, days: int = 60, timeout: float = 8.0) -> tuple[list[dict], str]:
    """Recent daily bars for home chart. EastMoney first, Sina fallback."""

    def _load_em() -> list[dict]:
        end = date.today()
        start = end - timedelta(days=max(days * 2, 90))
        df = _fetch_etf_hist(code, start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        if df is None or df.empty:
            return []
        tail = df.tail(days)
        return [
            {
                "open": float(r["开盘"]),
                "high": float(r["最高"]),
                "low": float(r["最低"]),
                "close": float(r["收盘"]),
            }
            for _, r in tail.iterrows()
        ]

    def _load_sina() -> list[dict]:
        import akshare as ak

        symbol = f"sh{code}"
        df = ak.fund_etf_hist_sina(symbol=symbol)
        if df is None or df.empty:
            return []
        tail = df.tail(days)
        return [
            {
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
            }
            for _, r in tail.iterrows()
        ]

    try:
        bars = market_cache.get_or_set(
            f"etf_ohlc_{code}_{days}d",
            ttl_sec=300,
            factory=lambda: _executor.submit(_load_em).result(timeout=timeout),
        )
        if bars:
            return bars, "eastmoney"
    except Exception as exc:
        logger.warning("fund_etf_ohlc %s failed: %s", code, exc)

    try:
        bars = market_cache.get_or_set(
            f"etf_ohlc_sina_{code}_{days}d",
            ttl_sec=300,
            factory=lambda: _executor.submit(_load_sina).result(timeout=timeout),
        )
        if bars:
            return bars, "sina"
    except Exception as exc:
        logger.warning("fund_etf_hist_sina %s failed: %s", code, exc)

    return [], "mock"
