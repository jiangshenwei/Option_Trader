import type { TradeLeg, TradeLegToggle } from "../types";

export interface ApiTradeLeg {
  key: string;
  code: string;
  direction: "long" | "short";
  quote_type: "mid" | "opponent" | "limit";
  qty: number;
  strike: number;
  month: string;
  is_call: boolean;
  iv: number | null;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  bid?: number | null;
  ask?: number | null;
}

export function fromApiTradeLeg(leg: ApiTradeLeg): TradeLeg {
  return {
    key: leg.key,
    code: leg.code,
    direction: leg.direction,
    quoteType: leg.quote_type,
    qty: leg.qty,
    strike: leg.strike,
    month: leg.month,
    isCall: leg.is_call,
    iv: leg.iv,
    delta: leg.delta,
    gamma: leg.gamma,
    theta: leg.theta,
    vega: leg.vega,
    bid: leg.bid,
    ask: leg.ask,
  };
}

export function toToggleApi(meta: Omit<TradeLeg, "direction" | "quoteType" | "qty">): TradeLegToggle {
  return {
    key: meta.key,
    code: meta.code,
    strike: meta.strike,
    month: meta.month,
    is_call: meta.isCall,
    iv: meta.iv,
    delta: meta.delta,
    gamma: meta.gamma,
    theta: meta.theta,
    vega: meta.vega,
    bid: meta.bid,
    ask: meta.ask,
  };
}

export function toPatchApi(patch: Partial<TradeLeg>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (patch.direction !== undefined) out.direction = patch.direction;
  if (patch.quoteType !== undefined) out.quote_type = patch.quoteType;
  if (patch.qty !== undefined) out.qty = patch.qty;
  if (patch.bid !== undefined) out.bid = patch.bid;
  if (patch.ask !== undefined) out.ask = patch.ask;
  return out;
}
