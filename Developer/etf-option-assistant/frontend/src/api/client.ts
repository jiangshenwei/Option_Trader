import type { HeatmapResponse, HomeCard, MarketStatus, Settings, TQuoteResponse, TradeLeg } from "../types";
import { fromApiTradeLeg, toPatchApi, toToggleApi, type ApiTradeLeg } from "./trade";

const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit, timeoutMs = 15000): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, { ...init, signal: controller.signal });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || res.statusText);
    }
    return res.json() as Promise<T>;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error("请求超时，请确认后端已启动 (uvicorn port 8000)");
    }
    throw e;
  } finally {
    clearTimeout(timeout);
  }
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  status: () => request<MarketStatus>("/status"),
  home: () => request<HomeCard[]>("/home", undefined, 45000),
  heatmap: (underlying: string) => request<HeatmapResponse>(`/heatmap/${underlying}`, undefined, 45000),
  tquote: (underlying: string, monthIdx = 0) =>
    request<TQuoteResponse>(`/tquote/${underlying}?month_idx=${monthIdx}`, undefined, 45000),
  getSettings: () => request<Settings>("/settings"),
  updateSettings: (body: Settings) =>
    request<Settings>("/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  getTrades: async () => {
    const rows = await request<ApiTradeLeg[]>("/trades");
    return rows.map(fromApiTradeLeg);
  },
  toggleTrade: async (meta: Omit<TradeLeg, "direction" | "quoteType" | "qty">) => {
    const rows = await request<ApiTradeLeg[]>("/trades/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toToggleApi(meta)),
    });
    return rows.map(fromApiTradeLeg);
  },
  patchTrade: async (key: string, patch: Partial<TradeLeg>) => {
    const rows = await request<ApiTradeLeg[]>(`/trades/${encodeURIComponent(key)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(toPatchApi(patch)),
    });
    return rows.map(fromApiTradeLeg);
  },
  deleteTrade: async (key: string) => {
    const rows = await request<ApiTradeLeg[]>(`/trades/${encodeURIComponent(key)}`, {
      method: "DELETE",
    });
    return rows.map(fromApiTradeLeg);
  },
};
