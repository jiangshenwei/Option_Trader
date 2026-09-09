from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Greeks(BaseModel):
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0


class OptionQuote(BaseModel):
    code: str
    name: str | None = None
    underlying: str
    option_type: Literal["C", "P"]
    strike: float
    expiry_year: int
    expiry_month: int
    days_to_expiry: float
    bid: float | None = None
    ask: float | None = None
    mid: float | None = None
    iv: float | None = None
    greeks: Greeks = Field(default_factory=Greeks)
    is_standard: bool = True


class UnderlyingQuote(BaseModel):
    code: str
    name: str
    spot: float
    change_pct: float = 0.0
    hv20: float | None = None


class MonthInfo(BaseModel):
    year: int
    month: int
    label: str
    short_label: str


class HeatmapAdjustedCell(BaseModel):
    strike: float
    iv: float | None
    delta: float | None
    state_key: str
    code: str | None = None
    name: str | None = None
    bid: float | None = None
    ask: float | None = None


class HeatmapCell(BaseModel):
    strike: float
    month: MonthInfo
    is_call: bool
    iv: float | None
    delta: float | None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    state_key: str
    code: str | None = None
    bid: float | None = None
    ask: float | None = None
    is_standard: bool = True


class HeatmapResponse(BaseModel):
    underlying: str
    spot: float
    strike_step: float
    months: list[MonthInfo]
    put_strikes: list[float]
    call_strikes: list[float]
    put_non_standard: list[float] = Field(default_factory=list)
    call_non_standard: list[float] = Field(default_factory=list)
    cells: list[HeatmapCell]
    vmin: float
    vmax: float
    hv20: float | None = None
    hv_history_start: str | None = None
    hv_history_end: str | None = None
    hv_trading_days: int | None = None
    iv_color_source: str = "mock"
    include_non_standard: bool = False
    updated_at: datetime


class TQuoteRow(BaseModel):
    strike: float
    is_standard: bool = True
    call: OptionQuote | None = None
    put: OptionQuote | None = None


class TQuoteResponse(BaseModel):
    underlying: str
    spot: float
    month: MonthInfo
    rows: list[TQuoteRow]
    include_non_standard: bool = False
    updated_at: datetime


class HomeUnderlyingCard(BaseModel):
    code: str
    name: str
    spot: float
    change_pct: float
    hv20: float | None = None
    ohlc: list[dict]
    spot_source: str = "mock"
    ohlc_source: str = "mock"


class SettingsModel(BaseModel):
    r: float = Field(0.02, ge=0, le=1)
    q: float = Field(0.0, ge=0, le=1)
    quote_refresh_sec: int = Field(8, ge=3, le=300)
    home_refresh_sec: int = Field(30, ge=5, le=600)
    show_non_standard: bool = False


class TradeLeg(BaseModel):
    key: str
    code: str
    direction: Literal["long", "short"]
    quote_type: Literal["mid", "opponent", "limit"] = "mid"
    qty: int = Field(1, ge=1)
    strike: float
    month: str
    is_call: bool
    iv: float | None = None
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    bid: float | None = None
    ask: float | None = None
    order_price: float | None = None
    premium: float | None = None


class TradeLegUpdate(BaseModel):
    direction: Literal["long", "short"] | None = None
    quote_type: Literal["mid", "opponent", "limit"] | None = None
    qty: int | None = Field(None, ge=1)
    bid: float | None = None
    ask: float | None = None


class TradeLegToggle(BaseModel):
    key: str
    code: str
    strike: float
    month: str
    is_call: bool
    iv: float | None = None
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    bid: float | None = None
    ask: float | None = None
