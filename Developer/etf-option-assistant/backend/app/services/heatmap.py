from __future__ import annotations

from datetime import datetime

from app.adapters.eastmoney import get_adapter
from app.analytics.months import get_sse_option_months
from app.analytics.strikes import build_strikes, merge_strike_axes
from app.models.schemas import HeatmapCell, HeatmapResponse, MonthInfo, OptionQuote, TQuoteResponse, TQuoteRow
from app.services.hv import get_hv_profile
from app.services.settings_store import load_settings


def _month_model(m: dict) -> MonthInfo:
    return MonthInfo(**m)


def _quote_map(quotes: list[OptionQuote]) -> dict[tuple, OptionQuote]:
    out: dict[tuple, OptionQuote] = {}
    for q in quotes:
        key = (q.expiry_year, q.expiry_month, round(q.strike, 4), q.option_type)
        existing = out.get(key)
        if existing is None or (existing.is_standard is False and q.is_standard):
            out[key] = q
    return out


def _cell_state_key(strike: float, month: MonthInfo, is_call: bool, quote: OptionQuote | None) -> str:
    side = "C" if is_call else "P"
    if quote and not quote.is_standard:
        return f"{side}_adj_{quote.code}_{month.short_label}_{strike}"
    return f"{side}_{strike}_{month.short_label}"


def build_heatmap(underlying: str) -> HeatmapResponse:
    adapter = get_adapter()
    settings = load_settings()
    spot = adapter.get_underlying_quote(underlying).spot
    months = [_month_model(m) for m in get_sse_option_months()]
    quotes = adapter.get_option_quotes(underlying, otm_only=True)
    strike_info = merge_strike_axes(spot, quotes, settings.show_non_standard)
    quote_map = _quote_map(quotes)
    std_puts = set(build_strikes(spot)["puts"])
    std_calls = set(build_strikes(spot)["calls"])

    cells: list[HeatmapCell] = []
    for month in months:
        for strike in strike_info["puts"]:
            q = quote_map.get((month.year, month.month, strike, "P"))
            is_std = strike in std_puts
            cells.append(
                HeatmapCell(
                    strike=strike,
                    month=month,
                    is_call=False,
                    iv=q.iv if q else None,
                    delta=q.greeks.delta if q else None,
                    gamma=q.greeks.gamma if q else None,
                    theta=q.greeks.theta if q else None,
                    vega=q.greeks.vega if q else None,
                    state_key=_cell_state_key(strike, month, False, q),
                    code=q.code if q else None,
                    bid=q.bid if q else None,
                    ask=q.ask if q else None,
                    is_standard=is_std,
                )
            )
        for strike in strike_info["calls"]:
            q = quote_map.get((month.year, month.month, strike, "C"))
            is_std = strike in std_calls
            cells.append(
                HeatmapCell(
                    strike=strike,
                    month=month,
                    is_call=True,
                    iv=q.iv if q else None,
                    delta=q.greeks.delta if q else None,
                    gamma=q.greeks.gamma if q else None,
                    theta=q.greeks.theta if q else None,
                    vega=q.greeks.vega if q else None,
                    state_key=_cell_state_key(strike, month, True, q),
                    code=q.code if q else None,
                    bid=q.bid if q else None,
                    ask=q.ask if q else None,
                    is_standard=is_std,
                )
            )

    hv_profile = get_hv_profile(underlying)
    if hv_profile.source in ("live", "mock"):
        vmin, vmax = hv_profile.vmin, hv_profile.vmax
        iv_color_source = "hv_percentile" if hv_profile.source == "live" else "mock"
    else:
        ivs = [c.iv for c in cells if c.iv is not None and c.is_standard]
        vmin = min(ivs) if ivs else hv_profile.vmin
        vmax = max(ivs) if ivs else hv_profile.vmax
        iv_color_source = "iv_range"

    return HeatmapResponse(
        underlying=underlying,
        spot=spot,
        strike_step=strike_info["step"],
        months=months,
        put_strikes=strike_info["puts"],
        call_strikes=strike_info["calls"],
        put_non_standard=strike_info["put_non_standard"],
        call_non_standard=strike_info["call_non_standard"],
        cells=cells,
        vmin=vmin,
        vmax=vmax,
        hv20=hv_profile.hv20,
        hv_history_start=hv_profile.history_start,
        hv_history_end=hv_profile.history_end,
        hv_trading_days=hv_profile.trading_days,
        iv_color_source=iv_color_source,
        include_non_standard=settings.show_non_standard,
        updated_at=datetime.now(),
    )


def build_tquote(underlying: str, month_idx: int = 0) -> TQuoteResponse:
    adapter = get_adapter()
    settings = load_settings()
    spot = adapter.get_underlying_quote(underlying).spot
    months = [_month_model(m) for m in get_sse_option_months()]
    month = months[min(month_idx, len(months) - 1)]
    quotes = adapter.get_option_quotes(underlying, otm_only=False)
    strike_info = merge_strike_axes(spot, quotes, settings.show_non_standard)
    quote_map = _quote_map(quotes)
    std_all = set(build_strikes(spot)["all"])

    rows: list[TQuoteRow] = []
    for k in strike_info["all"]:
        rows.append(
            TQuoteRow(
                strike=k,
                is_standard=k in std_all,
                call=quote_map.get((month.year, month.month, k, "C")),
                put=quote_map.get((month.year, month.month, k, "P")),
            )
        )

    return TQuoteResponse(
        underlying=underlying,
        spot=spot,
        month=month,
        rows=rows,
        include_non_standard=settings.show_non_standard,
        updated_at=datetime.now(),
    )
