from __future__ import annotations

import math
from typing import Literal

from scipy.stats import norm

OptionType = Literal["C", "P"]


def bs_option_price(
    option_type: OptionType,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    sigma: float,
) -> float:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(0.0, (S - K) if option_type == "C" else (K - S))
    d1 = (math.log(S / K) + (r - q + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if option_type == "C":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def implied_vol(
    option_type: OptionType,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    option_price: float,
    tol: float = 1e-4,
    max_iter: int = 100,
) -> float | None:
    if option_price <= 0 or T <= 0 or S <= 0 or K <= 0:
        return None
    lower, upper = 0.01, 5.0
    for _ in range(max_iter):
        mid = (lower + upper) / 2
        mid_price = bs_option_price(option_type, S, K, T, r, q, mid)
        if abs(mid_price - option_price) < tol:
            return mid
        if mid_price > option_price:
            upper = mid
        else:
            lower = mid
    return None
