from __future__ import annotations

import logging
import re
from datetime import date, datetime

import pandas as pd
import requests

from app.adapters.chain_parser import (
    _match_underlying,
    _parse_expiry_month,
    is_non_standard_option_name,
)

logger = logging.getLogger(__name__)

ETF_UNDERLYINGS = ("510050", "510300", "510500")
BATCH_SIZE = 80
_SINA_HEADERS = {
    "Referer": "https://stock.finance.sina.com.cn/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _fetch_sse_contracts() -> pd.DataFrame:
    import akshare as ak

    return ak.option_current_day_sse()


def _parse_sina_line(line: str) -> tuple[str, dict[str, float | None]] | None:
    if "hq_str_CON_OP_" not in line:
        return None
    match = re.search(r'hq_str_CON_OP_(\d+)="(.*)";', line)
    if not match:
        return None
    code, payload = match.group(1), match.group(2)
    parts = payload.split(",")
    if len(parts) < 9:
        return None

    def _num(idx: int) -> float | None:
        try:
            val = float(parts[idx])
            return val if val > 0 else None
        except (ValueError, IndexError):
            return None

    return code, {
        "bid": _num(1),
        "last": _num(2),
        "ask": _num(3),
        "prev_settle": _num(8),
    }


def _fetch_prices_batch(codes: list[str], timeout: float = 15.0) -> dict[str, dict[str, float | None]]:
    if not codes:
        return {}
    url = "https://hq.sinajs.cn/list=" + ",".join(f"CON_OP_{c}" for c in codes)
    try:
        response = requests.get(url, headers=_SINA_HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestError as exc:
        logger.warning("sina option batch request failed: %s", exc)
        return {}

    out: dict[str, dict[str, float | None]] = {}
    for line in response.text.strip().split("\n"):
        parsed = _parse_sina_line(line)
        if parsed:
            out[parsed[0]] = parsed[1]
    return out


def _days_to_expiry(expire_raw: str, ref: date | None = None) -> float:
    ref = ref or date.today()
    try:
        expire = datetime.strptime(str(expire_raw), "%Y%m%d").date()
        return float(max((expire - ref).days, 0))
    except ValueError:
        return 0.0


def _contract_passes_filters(
    underlying: str,
    name: str,
    strike: float,
    expiry_month: int | None,
    spot: float,
    listed_months: list[dict],
    strike_min: float,
    strike_max: float,
    otm_only: bool,
    include_non_standard: bool,
) -> bool:
    if expiry_month is None:
        return False
    u_name = name.split("购")[0].split("沽")[0]
    if _match_underlying(u_name) != underlying:
        return False
    is_std = not is_non_standard_option_name(name)
    if not include_non_standard and not is_std:
        return False
    month_set = {m["month"] for m in listed_months}
    if expiry_month not in month_set:
        return False
    if strike < strike_min or strike > strike_max:
        return False
    if "购" in name:
        opt_type = "C"
    elif "沽" in name:
        opt_type = "P"
    else:
        return False
    if otm_only:
        if opt_type == "C" and strike < spot:
            return False
        if opt_type == "P" and strike >= spot:
            return False
    return True


def build_option_chain_df(
    timeout: float = 20.0,
    *,
    underlying: str | None = None,
    spot: float | None = None,
    listed_months: list[dict] | None = None,
    strike_min: float | None = None,
    strike_max: float | None = None,
    otm_only: bool = False,
    include_non_standard: bool = False,
) -> pd.DataFrame:
    """Build option chain via SSE metadata + Sina quotes.

    When underlying/spot/months are provided, only matching contracts are priced
    (reduces API calls when include_non_standard=False).
    """

    contracts = _fetch_sse_contracts()
    if contracts is None or contracts.empty:
        return pd.DataFrame()

    subset = contracts[contracts["标的券名称及代码"].apply(
        lambda x: any(u in str(x) for u in ETF_UNDERLYINGS)
    )]
    if subset.empty:
        return pd.DataFrame()

    scoped = underlying is not None and spot is not None and listed_months is not None
    strike_lo = strike_min if strike_min is not None else 0.0
    strike_hi = strike_max if strike_max is not None else 1e9

    candidates: list[dict] = []
    for _, row in subset.iterrows():
        name = str(row["合约简称"])
        strike = float(row["行权价"])
        month = _parse_expiry_month(name)
        is_std = not is_non_standard_option_name(name)
        if scoped:
            if not _contract_passes_filters(
                underlying,
                name,
                strike,
                month,
                spot,
                listed_months,
                strike_lo,
                strike_hi,
                otm_only,
                include_non_standard,
            ):
                continue
        elif not include_non_standard and not is_std:
            continue

        candidates.append(
            {
                "code": str(row["合约编码"]),
                "name": name,
                "strike": strike,
                "expire": str(row["到期日"]),
                "is_standard": is_std,
            }
        )

    codes = [c["code"] for c in candidates]
    prices: dict[str, dict[str, float | None]] = {}
    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i : i + BATCH_SIZE]
        prices.update(_fetch_prices_batch(batch, timeout=min(timeout, 15.0)))

    rows: list[dict] = []
    for item in candidates:
        code = item["code"]
        quote = prices.get(code, {})
        rows.append(
            {
                "代码": code,
                "名称": item["name"],
                "行权价": item["strike"],
                "剩余日": _days_to_expiry(item["expire"]),
                "最新价": quote.get("last"),
                "昨结": quote.get("prev_settle"),
                "买一": quote.get("bid"),
                "卖一": quote.get("ask"),
                "is_standard": item["is_standard"],
            }
        )

    df = pd.DataFrame(rows)
    priced = df[df["最新价"].notna() & (df["最新价"] > 0)] if not df.empty else df
    logger.info(
        "sina option chain: scoped=%s include_adj=%s candidates=%s priced=%s",
        scoped,
        include_non_standard,
        len(candidates),
        len(priced),
    )
    return df
