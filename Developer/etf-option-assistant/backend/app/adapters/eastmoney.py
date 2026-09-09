from __future__ import annotations

import logging
from typing import Protocol

import pandas as pd

from app.adapters.chain_parser import (
    filter_chain,
    parse_option_dataframe,
)
from app.adapters.live_market import (
    fetch_etf_ohlc,
    fetch_etf_spots,
    fetch_option_chain_df,
    get_market_status,
)
from app.config import get_settings
from app.models.schemas import Greeks, HomeUnderlyingCard, OptionQuote, UnderlyingQuote
from app.services.hv import get_hv_profile

logger = logging.getLogger(__name__)

UNDERLYINGS = {
    "510050": {"name": "50ETF", "symbol": "sh510050"},
    "510300": {"name": "300ETF", "symbol": "sh510300"},
    "510500": {"name": "500ETF", "symbol": "sh510500"},
}

_MOCK_SPOTS = {
    "510050": (2.505, 0.82),
    "510300": (3.892, -0.35),
    "510500": (7.689, 1.12),
}


def _round_bar(bar: dict) -> dict:
    return {k: round(float(v), 4) for k, v in bar.items()}


class MarketDataAdapter(Protocol):
    def get_underlying_quote(self, code: str) -> UnderlyingQuote: ...
    def get_home_cards(self) -> list[HomeUnderlyingCard]: ...
    def get_option_quotes(self, underlying: str, otm_only: bool = True) -> list[OptionQuote]: ...


def _mock_ohlc(seed: float, n: int = 60) -> list[dict]:
    import math
    import random

    random.seed(int(seed * 1000))
    data = []
    price = seed
    for i in range(n):
        open_p = price
        change = (math.sin(i / 5 + seed) + (random.random() - 0.5) * 0.4) * 0.02
        close = max(0.5, open_p + change)
        high = max(open_p, close) + random.random() * 0.015
        low = min(open_p, close) - random.random() * 0.015
        data.append({"open": open_p, "high": high, "low": low, "close": close})
        price = close
    return data


class EastMoneyAdapter:
    """EastMoney via AKShare when live_data=True; otherwise mock for fast local dev."""

    def get_underlying_quote(self, code: str) -> UnderlyingQuote:
        meta = UNDERLYINGS.get(code)
        if not meta:
            raise ValueError(f"Unknown underlying: {code}")
        spot, chg = self._get_spot_chg(code)
        return UnderlyingQuote(code=code, name=meta["name"], spot=spot, change_pct=chg)

    def get_home_cards(self) -> list[HomeUnderlyingCard]:
        live_spots: dict[str, dict] = {}
        if get_settings().live_data:
            live_spots = fetch_etf_spots(timeout=5.0)

        cards: list[HomeUnderlyingCard] = []
        for code in UNDERLYINGS:
            mock_spot, mock_chg = _MOCK_SPOTS.get(code, (3.0, 0.0))
            spot, chg = mock_spot, mock_chg
            spot_source = "mock"
            live = live_spots.get(code)
            if live:
                spot, chg = live["spot"], live["chg"]
                spot_source = live.get("source", "live")

            ohlc, ohlc_source = self._get_ohlc(code, spot)
            hv_profile = get_hv_profile(code)
            cards.append(
                HomeUnderlyingCard(
                    code=code,
                    name=UNDERLYINGS[code]["name"],
                    spot=round(spot, 4),
                    change_pct=round(chg, 4),
                    hv20=hv_profile.hv20,
                    ohlc=ohlc,
                    spot_source=spot_source,
                    ohlc_source=ohlc_source,
                )
            )
        return cards

    def get_option_quotes(self, underlying: str, otm_only: bool = True) -> list[OptionQuote]:
        settings = get_settings()
        if settings.live_data:
            live = self._get_live_option_quotes(underlying, otm_only=otm_only)
            if live:
                return live
            logger.warning("Live option chain empty for %s, falling back to mock", underlying)
        return self._get_mock_option_quotes(underlying, otm_only=otm_only)

    def _get_spot_chg(self, code: str) -> tuple[float, float]:
        spot, chg = _MOCK_SPOTS.get(code, (3.0, 0.0))
        if not get_settings().live_data:
            return spot, chg
        live = fetch_etf_spots().get(code)
        if live:
            return live["spot"], live["chg"]
        return spot, chg

    def _get_ohlc(self, code: str, spot: float) -> tuple[list[dict], str]:
        if get_settings().live_data:
            ohlc, source = fetch_etf_ohlc(code)
            if ohlc:
                return [_round_bar(b) for b in ohlc], source
        return _mock_ohlc(spot), "mock"

    def _get_live_option_quotes(self, underlying: str, otm_only: bool = True) -> list[OptionQuote]:
        from app.analytics.greeks import quote_analytics
        from app.analytics.months import get_sse_option_months
        from app.analytics.strikes import build_strikes
        from app.services.settings_store import load_settings

        spot = self.get_underlying_quote(underlying).spot
        settings = load_settings()
        months = get_sse_option_months()
        strike_info = build_strikes(spot)
        strike_min = strike_info["all"][0] if strike_info["all"] else spot * 0.8
        strike_max = strike_info["all"][-1] if strike_info["all"] else spot * 1.2
        df = fetch_option_chain_df(
            underlying=underlying,
            spot=spot,
            listed_months=months,
            strike_min=strike_min,
            strike_max=strike_max,
            otm_only=otm_only,
            include_non_standard=settings.show_non_standard,
        )
        if df is None or df.empty:
            return []

        parsed = parse_option_dataframe(df)
        filtered = filter_chain(
            parsed,
            underlying,
            spot,
            months,
            strike_min,
            strike_max,
            otm_only=otm_only,
            include_non_standard=settings.show_non_standard,
        )
        month_lookup = {m["month"]: m for m in months}
        quotes: list[OptionQuote] = []
        bid_col = df["买一"] if "买一" in df.columns else None
        ask_col = df["卖一"] if "卖一" in df.columns else None
        code_to_ba: dict[str, tuple[float | None, float | None]] = {}
        if bid_col is not None and ask_col is not None:
            for _, r in df.iterrows():
                code_to_ba[str(r["代码"])] = (
                    float(r["买一"]) if pd.notna(r.get("买一")) and r.get("买一") else None,
                    float(r["卖一"]) if pd.notna(r.get("卖一")) and r.get("卖一") else None,
                )

        for row in filtered:
            month_meta = month_lookup.get(row.expiry_month)
            if not month_meta:
                continue
            t = max(row.days_to_expiry / 365, 1 / 365)
            price = row.last_price or 0
            if price <= 0:
                continue
            bid = ask = round(price, 4)
            ba = code_to_ba.get(row.code)
            if ba:
                bid = ba[0] or bid
                ask = ba[1] or ask
            opt_type = row.option_type
            analytics = quote_analytics(opt_type, spot, row.strike, t, settings.r, settings.q, bid, ask)
            quotes.append(
                OptionQuote(
                    code=row.code,
                    name=row.name,
                    underlying=underlying,
                    option_type=opt_type,
                    strike=row.strike,
                    expiry_year=month_meta["year"],
                    expiry_month=month_meta["month"],
                    days_to_expiry=row.days_to_expiry,
                    bid=bid,
                    ask=ask,
                    mid=analytics["mid"],
                    iv=analytics["iv"],
                    is_standard=row.is_standard,
                    greeks=Greeks(
                        delta=analytics["delta"],
                        gamma=analytics["gamma"],
                        theta=analytics["theta"],
                        vega=analytics["vega"],
                    ),
                )
            )
        return self._enrich_quotes_with_sina(quotes, spot, settings.r, settings.q)

    def _enrich_quotes_with_sina(
        self,
        quotes: list[OptionQuote],
        spot: float,
        r: float,
        q: float,
    ) -> list[OptionQuote]:
        from app.adapters.sina_quote import fetch_bid_ask_batch
        from app.analytics.greeks import quote_analytics
        from app.config import get_settings

        if not get_settings().sina_auxiliary or not quotes:
            return quotes

        sina_map = fetch_bid_ask_batch([q.code for q in quotes])
        if not sina_map:
            return quotes

        enriched: list[OptionQuote] = []
        for quote in quotes:
            ba = sina_map.get(quote.code)
            if not ba:
                enriched.append(quote)
                continue
            bid, ask = ba
            bid = bid or quote.bid
            ask = ask or quote.ask
            if not bid or not ask:
                enriched.append(quote)
                continue
            t = max(quote.days_to_expiry / 365, 1 / 365)
            analytics = quote_analytics(quote.option_type, spot, quote.strike, t, r, q, bid, ask)
            enriched.append(
                quote.model_copy(
                    update={
                        "bid": bid,
                        "ask": ask,
                        "mid": analytics["mid"],
                        "iv": analytics["iv"],
                        "greeks": Greeks(
                            delta=analytics["delta"],
                            gamma=analytics["gamma"],
                            theta=analytics["theta"],
                            vega=analytics["vega"],
                        ),
                    }
                )
            )
        return enriched

    def _get_mock_option_quotes(self, underlying: str, otm_only: bool = True) -> list[OptionQuote]:
        from app.analytics.greeks import quote_analytics
        from app.analytics.months import get_sse_option_months
        from app.analytics.strikes import build_strikes
        from app.services.settings_store import load_settings

        spot = self.get_underlying_quote(underlying).spot
        settings = load_settings()
        strikes = build_strikes(spot)["all"]
        months = get_sse_option_months()
        quotes: list[OptionQuote] = []

        for mi, month in enumerate(months):
            t = max((mi + 1) * 30 / 365, 1 / 365)
            for k in strikes:
                for is_call in (True, False):
                    if otm_only:
                        if is_call and k < spot:
                            continue
                        if not is_call and k >= spot:
                            continue
                    opt_type = "C" if is_call else "P"
                    intrinsic = max(spot - k, 0) if is_call else max(k - spot, 0)
                    bid = round(intrinsic + 0.05 + abs(spot - k) * 0.01 + mi * 0.01, 4)
                    ask = round(bid + 0.003, 4)
                    analytics = quote_analytics(opt_type, spot, k, t, settings.r, settings.q, bid, ask)
                    code = f"{underlying}{'购' if is_call else '沽'}{month['short_label']}{str(k).replace('.', '')}"
                    name = f"{UNDERLYINGS[underlying]['name']}{'购' if is_call else '沽'}{month['month']}月{str(k).replace('.', '')}"
                    quotes.append(
                        OptionQuote(
                            code=code,
                            name=name,
                            underlying=underlying,
                            option_type=opt_type,
                            strike=k,
                            expiry_year=month["year"],
                            expiry_month=month["month"],
                            days_to_expiry=t * 365,
                            bid=bid,
                            ask=ask,
                            mid=analytics["mid"],
                            iv=analytics["iv"],
                            is_standard=True,
                            greeks=Greeks(
                                delta=analytics["delta"],
                                gamma=analytics["gamma"],
                                theta=analytics["theta"],
                                vega=analytics["vega"],
                            ),
                        )
                    )
        if settings.show_non_standard and months and strikes:
            month = months[0]
            t = max(30 / 365, 1 / 365)
            for i in range(len(strikes) - 1):
                k0, k1 = strikes[i], strikes[i + 1]
                mid = round((k0 + k1) / 2, 4)
                for is_call in (True, False):
                    if otm_only:
                        if is_call and mid < spot:
                            continue
                        if not is_call and mid >= spot:
                            continue
                    opt_type = "C" if is_call else "P"
                    bid = round(0.06 + abs(spot - mid) * 0.012, 4)
                    ask = round(bid + 0.004, 4)
                    analytics = quote_analytics(opt_type, spot, mid, t, settings.r, settings.q, bid, ask)
                    suffix = str(mid).replace(".", "")
                    code = f"{underlying}{'购' if is_call else '沽'}{month['short_label']}{suffix}A"
                    name = (
                        f"{UNDERLYINGS[underlying]['name']}{'购' if is_call else '沽'}"
                        f"{month['month']}月{suffix}A"
                    )
                    quotes.append(
                        OptionQuote(
                            code=code,
                            name=name,
                            underlying=underlying,
                            option_type=opt_type,
                            strike=mid,
                            expiry_year=month["year"],
                            expiry_month=month["month"],
                            days_to_expiry=t * 365,
                            bid=bid,
                            ask=ask,
                            mid=analytics["mid"],
                            iv=analytics["iv"],
                            is_standard=False,
                            greeks=Greeks(
                                delta=analytics["delta"],
                                gamma=analytics["gamma"],
                                theta=analytics["theta"],
                                vega=analytics["vega"],
                            ),
                        )
                    )
        return quotes


def get_adapter() -> MarketDataAdapter:
    return EastMoneyAdapter()


def get_data_status() -> dict:
    from app.config import get_env_diagnostics

    settings = get_settings()
    market = get_market_status()
    return {
        "live_data": settings.live_data,
        "sina_auxiliary": settings.sina_auxiliary,
        "data_mode": "live" if settings.live_data else "mock",
        **market,
        "config": get_env_diagnostics(),
    }
