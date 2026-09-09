import { NavLink, Outlet, useLocation, useNavigate, type NavigateFunction } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { MarketStatus } from "../types";

export interface LayoutContextValue {
  underlying: string;
  navigate: NavigateFunction;
}

const TITLES: Record<string, string> = {
  "/": "首页",
  "/heatmap": "IV 热力图",
  "/tquote": "T 型报价",
  "/tradelist": "交易列表",
  "/settings": "设置",
};

export default function MainLayout() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [underlying, setUnderlying] = useState("510500");
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null);
  const showToolbar = !["/", "/settings"].includes(pathname);

  useEffect(() => {
    const saved = localStorage.getItem("underlying");
    if (saved) setUnderlying(saved);
  }, []);

  useEffect(() => {
    api.status()
      .then(setMarketStatus)
      .catch(() => setMarketStatus(null));
    const timer = setInterval(() => {
      api.status().then(setMarketStatus).catch(() => undefined);
    }, 30000);
    return () => clearInterval(timer);
  }, []);

  const onUnderlyingChange = (code: string) => {
    setUnderlying(code);
    localStorage.setItem("underlying", code);
    window.dispatchEvent(new CustomEvent("underlying-change", { detail: code }));
  };

  const onRefresh = () => {
    window.dispatchEvent(new CustomEvent("page-refresh", { detail: pathname }));
  };

  const chainLabel = (() => {
    if (!marketStatus || marketStatus.data_mode !== "live") return "";
    const src = marketStatus.chain_source;
    if (src === "sina") return " · 期权链新浪";
    if (src === "eastmoney") return " · 期权链东财";
    if (src === "mock") return " · 期权链模拟";
    return "";
  })();

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>ETF 期权助手</h1>
        <p className="sub">v0.1 开发版</p>
        <NavLink to="/" className={({ isActive }) => `nav-item${isActive ? " active" : ""}`} end>首页</NavLink>
        <NavLink to="/heatmap" className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}>IV 热力图</NavLink>
        <NavLink to="/tquote" className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}>T 型报价</NavLink>
        <NavLink to="/tradelist" className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}>交易列表</NavLink>
        <NavLink to="/settings" className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}>设置</NavLink>
      </aside>
      <div className="main">
        <header className="topbar">
          <h2>{TITLES[pathname] || "ETF 期权助手"}</h2>
          <div className="topbar-actions">
            {showToolbar && (
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <select className="chip" value={underlying} onChange={(e) => onUnderlyingChange(e.target.value)}>
                  <option value="510050">510050 50ETF</option>
                  <option value="510300">510300 300ETF</option>
                  <option value="510500">510500 500ETF</option>
                </select>
                <button className="chip" onClick={onRefresh}>刷新</button>
              </div>
            )}
            <span title={marketStatus?.chain_error || undefined}>
              <span className={`status-dot${marketStatus?.data_mode === "mock" ? " mock" : ""}`} />
              <span className="muted">
                {marketStatus?.data_mode === "live" ? "实时行情" : "模拟数据"}
                {chainLabel}
                {marketStatus?.chain_error ? " (链异常)" : ""}
              </span>
            </span>
          </div>
        </header>
        <div className="content">
          <Outlet context={{ underlying, navigate }} />
        </div>
      </div>
    </div>
  );
}

export function useLayoutContext() {
  return { underlying: localStorage.getItem("underlying") || "510500" };
}
