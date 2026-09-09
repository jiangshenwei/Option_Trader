from __future__ import annotations

from datetime import date, datetime


def strike_step(spot: float) -> float:
    if spot <= 3:
        return 0.05
    if spot <= 5:
        return 0.1
    if spot <= 10:
        return 0.25
    if spot <= 20:
        return 0.5
    if spot <= 50:
        return 1.0
    if spot <= 100:
        return 2.5
    return 5.0


def build_strikes(spot: float, pct: float = 0.2) -> dict:
    step = strike_step(spot)
    min_k = spot * (1 - pct)
    max_k = spot * (1 + pct)
    k = math.ceil(min_k / step) * step
    all_strikes: list[float] = []
    while k <= max_k + 1e-9:
        all_strikes.append(round(k, 4))
        k += step
    return {
        "puts": [x for x in all_strikes if x < spot],
        "calls": [x for x in all_strikes if x >= spot],
        "step": step,
        "all": all_strikes,
    }


def merge_strike_axes(
    spot: float,
    quotes: list,
    include_non_standard: bool,
    pct: float = 0.2,
) -> dict:
    """Standard ±20% grid; when enabled, append non-standard contract strikes as extra columns."""
    base = build_strikes(spot, pct)
    if not include_non_standard:
        return {
            **base,
            "put_non_standard": [],
            "call_non_standard": [],
        }

    min_k = spot * (1 - pct)
    max_k = spot * (1 + pct)
    std_puts = set(base["puts"])
    std_calls = set(base["calls"])
    put_extra: set[float] = set()
    call_extra: set[float] = set()

    for q in quotes:
        if q.is_standard:
            continue
        strike = round(float(q.strike), 4)
        if strike < min_k or strike > max_k:
            continue
        if q.option_type == "P" and strike < spot:
            put_extra.add(strike)
        elif q.option_type == "C" and strike >= spot:
            call_extra.add(strike)

    puts = sorted(std_puts | put_extra)
    calls = sorted(std_calls | call_extra)
    return {
        "puts": puts,
        "calls": calls,
        "all": sorted(set(puts) | set(calls)),
        "step": base["step"],
        "put_non_standard": [k for k in puts if k not in std_puts],
        "call_non_standard": [k for k in calls if k not in std_calls],
    }


import math  # noqa: E402 — keep helpers grouped
