from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.db.database import connect
from app.models.schemas import TradeLeg, TradeLegToggle


def _row_to_leg(row: sqlite3.Row) -> TradeLeg:
    return TradeLeg(
        key=row["leg_key"],
        code=row["code"],
        direction=row["direction"],
        quote_type=row["quote_type"],
        qty=row["qty"],
        strike=row["strike"],
        month=row["month"],
        is_call=bool(row["is_call"]),
        iv=row["iv"],
        delta=row["delta"],
        gamma=row["gamma"],
        theta=row["theta"],
        vega=row["vega"],
        bid=row["bid"],
        ask=row["ask"],
    )


def list_trades() -> list[TradeLeg]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM trade_legs ORDER BY sort_order ASC, id ASC"
        ).fetchall()
    return [_row_to_leg(r) for r in rows]


def replace_trades(legs: list[TradeLeg]) -> list[TradeLeg]:
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute("DELETE FROM trade_legs")
        for idx, leg in enumerate(legs):
            conn.execute(
                """
                INSERT INTO trade_legs (
                    leg_key, code, direction, quote_type, qty, strike, month, is_call,
                    iv, delta, gamma, theta, vega, bid, ask, sort_order, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    leg.key,
                    leg.code,
                    leg.direction,
                    leg.quote_type,
                    leg.qty,
                    leg.strike,
                    leg.month,
                    int(leg.is_call),
                    leg.iv,
                    leg.delta,
                    leg.gamma,
                    leg.theta,
                    leg.vega,
                    leg.bid,
                    leg.ask,
                    idx,
                    now,
                ),
            )
        conn.commit()
    return list_trades()


def toggle_trade(leg: TradeLegToggle) -> list[TradeLeg]:
    current = list_trades()
    idx = next((i for i, item in enumerate(current) if item.key == leg.key), -1)
    if idx == -1:
        new_leg = TradeLeg(
            key=leg.key,
            code=leg.code,
            direction="long",
            quote_type="mid",
            qty=1,
            strike=leg.strike,
            month=leg.month,
            is_call=leg.is_call,
            iv=leg.iv,
            delta=leg.delta,
            gamma=leg.gamma,
            theta=leg.theta,
            vega=leg.vega,
            bid=leg.bid,
            ask=leg.ask,
        )
        return replace_trades(current + [new_leg])
    existing = current[idx]
    if existing.direction == "long":
        current[idx] = existing.model_copy(update={"direction": "short"})
        return replace_trades(current)
    return replace_trades([item for i, item in enumerate(current) if i != idx])


def update_trade(key: str, patch: dict) -> list[TradeLeg]:
    allowed = {"direction", "quote_type", "qty", "bid", "ask"}
    fields = {k: v for k, v in patch.items() if k in allowed}
    if not fields:
        return list_trades()
    sets = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [datetime.now(timezone.utc).isoformat(), key]
    with connect() as conn:
        conn.execute(f"UPDATE trade_legs SET {sets}, updated_at = ? WHERE leg_key = ?", values)
        conn.commit()
    return list_trades()


def delete_trade(key: str) -> list[TradeLeg]:
    with connect() as conn:
        conn.execute("DELETE FROM trade_legs WHERE leg_key = ?", (key,))
        conn.commit()
    return list_trades()
