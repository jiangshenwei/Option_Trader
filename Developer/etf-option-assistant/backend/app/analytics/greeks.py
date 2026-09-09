from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

from app.analytics.bs import OptionType, implied_vol


def mid_price(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None or bid <= 0 or ask <= 0:
        return None
    return round((bid + ask) / 2, 4)


def compute_greeks(
    option_type: OptionType,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    sigma: float,
) -> dict[str, float]:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    pdf = norm.pdf(d1)
    if option_type == "C":
        delta = math.exp(-q * T) * norm.cdf(d1)
        theta = (
            -(S * sigma * math.exp(-q * T) * pdf) / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * norm.cdf(d2)
        )
    else:
        delta = -math.exp(-q * T) * norm.cdf(-d1)
        theta = (
            -(S * sigma * math.exp(-q * T) * pdf) / (2 * math.sqrt(T))
            + r * K * math.exp(-r * T) * norm.cdf(-d2)
        )
    gamma = math.exp(-q * T) * pdf / (S * sigma * math.sqrt(T)) * S / 100
    vega = S * math.sqrt(T) * math.exp(-q * T) * pdf
    return {
        "delta": float(delta),
        "gamma": float(gamma),
        "theta": float(theta),
        "vega": float(vega),
    }


def quote_analytics(
    option_type: OptionType,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float,
    bid: float | None,
    ask: float | None,
) -> dict:
    mid = mid_price(bid, ask)
    iv = implied_vol(option_type, S, K, T, r, q, mid) if mid else None
    greeks = compute_greeks(option_type, S, K, T, r, q, iv or 0.2) if iv else {
        "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0
    }
    return {
        "bid": bid,
        "ask": ask,
        "mid": mid,
        "iv": round(iv * 100, 2) if iv else None,
        **greeks,
    }
