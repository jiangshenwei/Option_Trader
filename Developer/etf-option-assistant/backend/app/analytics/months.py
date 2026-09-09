from __future__ import annotations

import math
from datetime import date


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


QUARTERS = (3, 6, 9, 12)


def get_sse_option_months(ref: date | None = None) -> list[dict]:
    ref = ref or date.today()
    y0, m0 = ref.year, ref.month

    def add_month(y: int, m: int, delta: int) -> tuple[int, int]:
        nm = m + delta
        ny = y + (nm - 1) // 12
        nm = (nm - 1) % 12 + 1
        return ny, nm

    cur = (y0, m0)
    nxt = add_month(y0, m0, 1)
    quarter_slots: list[tuple[int, int]] = []
    for y in range(nxt[0], nxt[0] + 2):
        for q in QUARTERS:
            if y == nxt[0] and q <= nxt[1]:
                continue
            quarter_slots.append((y, q))

    raw = [cur, nxt, quarter_slots[0], quarter_slots[1]]
    seen: set[tuple[int, int]] = set()
    uniq: list[tuple[int, int]] = []
    for item in raw:
        if item not in seen:
            seen.add(item)
            uniq.append(item)

    result = []
    for y, m in uniq[:4]:
        if m == m0 and y == y0:
            label = f"{m}月(当月)"
        elif (y, m) == nxt:
            label = f"{m}月(下月)"
        else:
            label = f"{y}年{m}月(季)" if y != y0 else f"{m}月(季)"
        result.append({"year": y, "month": m, "label": label, "short_label": f"{m}月"})
    return result
