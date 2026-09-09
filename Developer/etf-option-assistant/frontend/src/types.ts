export interface Greeks {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
}

export interface MonthInfo {
  year: number;
  month: number;
  label: string;
  short_label: string;
}

export interface HeatmapCell {
  strike: number;
  month: MonthInfo;
  is_call: boolean;
  iv: number | null;
  delta: number | null;
  gamma?: number | null;
  theta?: number | null;
  vega?: number | null;
  state_key: string;
  code?: string | null;
  bid?: number | null;
  ask?: number | null;
  is_standard?: boolean;
}

export interface HeatmapResponse {
  underlying: string;
  spot: number;
  strike_step: number;
  months: MonthInfo[];
  put_strikes: number[];
  call_strikes: number[];
  put_non_standard?: number[];
  call_non_standard?: number[];
  cells: HeatmapCell[];
  vmin: number;
  vmax: number;
  hv20?: number | null;
  hv_history_start?: string | null;
  hv_history_end?: string | null;
  hv_trading_days?: number | null;
  iv_color_source?: string;
  include_non_standard?: boolean;
  updated_at: string;
}

export interface OptionQuote {
  code: string;
  name?: string | null;
  option_type: "C" | "P";
  strike: number;
  bid: number | null;
  ask: number | null;
  mid: number | null;
  iv: number | null;
  greeks: Greeks;
  is_standard?: boolean;
}

export interface TQuoteRow {
  strike: number;
  is_standard?: boolean;
  call: OptionQuote | null;
  put: OptionQuote | null;
}

export interface TQuoteResponse {
  underlying: string;
  spot: number;
  month: MonthInfo;
  rows: TQuoteRow[];
  include_non_standard?: boolean;
  updated_at: string;
}

export interface HomeCard {
  code: string;
  name: string;
  spot: number;
  change_pct: number;
  hv20: number | null;
  ohlc: { open: number; high: number; low: number; close: number }[];
  spot_source?: string;
  ohlc_source?: string;
}

export interface Settings {
  r: number;
  q: number;
  quote_refresh_sec: number;
  home_refresh_sec: number;
  show_non_standard: boolean;
}

export interface MarketStatus {
  live_data: boolean;
  data_mode: "live" | "mock";
  chain_source: string;
  chain_updated_at: string | null;
  chain_error: string | null;
}

export interface TradeLeg {
  key: string;
  code: string;
  direction: "long" | "short";
  quoteType: "mid" | "opponent" | "limit";
  qty: number;
  strike: number;
  month: string;
  isCall: boolean;
  iv: number | null;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  bid?: number | null;
  ask?: number | null;
}

export interface TradeLegToggle {
  key: string;
  code: string;
  strike: number;
  month: string;
  is_call: boolean;
  iv?: number | null;
  delta?: number;
  gamma?: number;
  theta?: number;
  vega?: number;
  bid?: number | null;
  ask?: number | null;
}
