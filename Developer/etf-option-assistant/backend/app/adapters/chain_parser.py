from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import pandas as pd

UNDERLYING_NAME_KEYS = {
    "510050": ("50ETF",),
    "510300": ("300ETF",),
    "510500": ("500ETF",),
}


@dataclass
class ParsedOptionRow:
    code: str
    name: str
    underlying: str
    option_type: str  # C or P
    strike: float
    days_to_expiry: float
    expiry_month: int
    last_price: float | None
    prev_settle: float | None
    is_standard: bool = True


def is_non_standard_option_name(name: str) -> bool:
    """Adjusted contracts after corporate action often suffix strike with a letter (e.g. 2650A)."""
    return bool(re.search(r"购\d+月[\d.]+[A-Za-z]$", name) or re.search(r"沽\d+月[\d.]+[A-Za-z]$", name))


def _is_sse_option_code(code: str) -> bool:
    return bool(re.match(r"^\d{8}$", str(code)))


def _split_name(name: str) -> tuple[str, str]:
    parts = re.split(r"(沽|购)", name)
    if len(parts) < 3:
        return name, ""
    return parts[0], parts[1]


def _match_underlying(underlying_name: str) -> str | None:
    name = underlying_name.upper().replace("XD", "")
    for code, keys in UNDERLYING_NAME_KEYS.items():
        for key in keys:
            if key.upper() in name:
                return code
    return None


def _parse_expiry_month(name: str) -> int | None:
    m = re.search(r"(\d{1,2})月", name)
    return int(m.group(1)) if m else None


def parse_option_dataframe(df: pd.DataFrame) -> list[ParsedOptionRow]:
    rows: list[ParsedOptionRow] = []
    if df is None or df.empty:
        return rows

    work = df[df["代码"].apply(_is_sse_option_code)].copy()
    for _, r in work.iterrows():
        name = str(r.get("名称", ""))
        u_name, direction_cn = _split_name(name)
        underlying = _match_underlying(u_name)
        if not underlying or direction_cn not in ("购", "沽"):
            continue
        opt_type = "C" if direction_cn == "购" else "P"
        strike = float(r.get("行权价", 0) or 0)
        if strike <= 0:
            continue
        month = _parse_expiry_month(name)
        if month is None:
            continue
        days = float(r.get("剩余日", 0) or 0)
        last_price = r.get("最新价")
        last_price = float(last_price) if pd.notna(last_price) and last_price else None
        prev = r.get("昨结")
        prev_settle = float(prev) if pd.notna(prev) and prev else None
        is_std = r.get("is_standard")
        if is_std is None or (isinstance(is_std, float) and pd.isna(is_std)):
            is_standard = not is_non_standard_option_name(name)
        else:
            is_standard = bool(is_std)
        rows.append(
            ParsedOptionRow(
                code=str(r["代码"]),
                name=name,
                underlying=underlying,
                option_type=opt_type,
                strike=strike,
                days_to_expiry=days,
                expiry_month=month,
                last_price=last_price,
                prev_settle=prev_settle,
                is_standard=is_standard,
            )
        )
    return rows


def filter_chain(
    rows: list[ParsedOptionRow],
    underlying: str,
    spot: float,
    listed_months: list[dict],
    strike_min: float,
    strike_max: float,
    otm_only: bool = True,
    include_non_standard: bool = False,
) -> list[ParsedOptionRow]:
    month_set = {m["month"] for m in listed_months}
    out: list[ParsedOptionRow] = []
    for row in rows:
        if row.underlying != underlying:
            continue
        if not include_non_standard and not row.is_standard:
            continue
        if row.expiry_month not in month_set:
            continue
        if row.strike < strike_min or row.strike > strike_max:
            continue
        if otm_only:
            if row.option_type == "C" and row.strike < spot:
                continue
            if row.option_type == "P" and row.strike >= spot:
                continue
        if row.last_price is None or row.last_price <= 0:
            continue
        out.append(row)
    return out


def nearest_grid_strike(strike: float, grid_strikes: list[float]) -> float | None:
    if not grid_strikes:
        return None
    return min(grid_strikes, key=lambda g: abs(g - strike))


def expiry_year_for_month(month: int, ref: date | None = None) -> int:
    ref = ref or date.today()
    y = ref.year
    if month < ref.month:
        y += 1
    return y
