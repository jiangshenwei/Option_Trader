import { useCallback, useEffect, useState } from "react";
import { Route, Routes, useOutletContext } from "react-router-dom";
import { api } from "./api/client";
import MainLayout, { type LayoutContextValue } from "./layouts/MainLayout";
import HeatmapPage from "./pages/HeatmapPage";
import HomePage from "./pages/HomePage";
import SettingsPage from "./pages/SettingsPage";
import TQuotePage from "./pages/TQuotePage";
import TradeListPage from "./pages/TradeListPage";
import type { HeatmapResponse, MonthInfo, TQuoteResponse } from "./types";

function HeatmapRoute() {
  const { underlying } = useOutletContext<LayoutContextValue>();
  const [data, setData] = useState<HeatmapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    api.heatmap(underlying)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [underlying]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const onRefresh = (e: Event) => {
      const ev = e as CustomEvent<string>;
      if (ev.detail === "/heatmap") load();
    };
    const onUnderlyingChange = () => load();
    window.addEventListener("page-refresh", onRefresh);
    window.addEventListener("underlying-change", onUnderlyingChange);
    return () => {
      window.removeEventListener("page-refresh", onRefresh);
      window.removeEventListener("underlying-change", onUnderlyingChange);
    };
  }, [load]);

  if (error) return <p className="muted">加载失败：{error}</p>;
  if (!data) return <p className="muted">加载中…</p>;
  return <HeatmapPage data={data} />;
}

function TQuoteRoute() {
  const { underlying } = useOutletContext<LayoutContextValue>();
  const [monthIdx, setMonthIdx] = useState(0);
  const [months, setMonths] = useState<MonthInfo[]>([]);
  const [data, setData] = useState<TQuoteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadMonths = useCallback(() => {
    api.heatmap(underlying)
      .then((h) => setMonths(h.months))
      .catch(() => {});
  }, [underlying]);

  const loadQuote = useCallback(() => {
    setError(null);
    api.tquote(underlying, monthIdx)
      .then(setData)
      .catch((e: Error) => setError(e.message));
  }, [underlying, monthIdx]);

  const loadAll = useCallback(() => {
    loadMonths();
    loadQuote();
  }, [loadMonths, loadQuote]);

  useEffect(() => {
    setMonthIdx(0);
  }, [underlying]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    loadQuote();
  }, [loadQuote]);

  useEffect(() => {
    const onRefresh = (e: Event) => {
      const ev = e as CustomEvent<string>;
      if (ev.detail === "/tquote") loadAll();
    };
    const onUnderlyingChange = () => {
      setMonthIdx(0);
      loadAll();
    };
    window.addEventListener("page-refresh", onRefresh);
    window.addEventListener("underlying-change", onUnderlyingChange);
    return () => {
      window.removeEventListener("page-refresh", onRefresh);
      window.removeEventListener("underlying-change", onUnderlyingChange);
    };
  }, [loadAll]);

  if (error) return <p className="muted">加载失败：{error}</p>;
  if (!data) return <p className="muted">加载中…</p>;

  return (
    <TQuotePage
      data={data}
      months={months.length ? months : [data.month]}
      monthIdx={monthIdx}
      onMonthChange={setMonthIdx}
    />
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<HomePage />} />
        <Route path="heatmap" element={<HeatmapRoute />} />
        <Route path="tquote" element={<TQuoteRoute />} />
        <Route path="tradelist" element={<TradeListPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
