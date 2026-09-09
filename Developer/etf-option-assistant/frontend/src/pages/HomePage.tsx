import { useCallback, useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../api/client";
import type { LayoutContextValue } from "../layouts/MainLayout";
import type { HomeCard } from "../types";

function sourceLabel(src?: string) {
  if (src === "eastmoney") return "现价·东财";
  if (src === "sina") return "现价·新浪";
  if (src === "mock") return "现价·模拟";
  return src || "";
}

function ohlcLabel(src?: string) {
  if (src === "eastmoney") return "K线·东财";
  if (src === "sina") return "K线·新浪";
  if (src === "mock") return "K线·模拟";
  return src || "";
}

function drawCandles(canvas: HTMLCanvasElement, ohlc: HomeCard["ohlc"]) {
  const ctx = canvas.getContext("2d");
  if (!ctx || !ohlc.length) return;

  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const pad = { l: 8, r: 8, t: 20, b: 16 };
  const plotW = w - pad.l - pad.r;
  const plotH = h - pad.t - pad.b;
  const visible = ohlc.slice(-40);
  const lows = visible.map((d) => d.low);
  const highs = visible.map((d) => d.high);
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const range = max - min || 0.01;

  const y = (v: number) => pad.t + plotH - ((v - min) / range) * plotH;
  const candleW = Math.max(4, plotW / visible.length - 2);

  ctx.fillStyle = "#64748b";
  ctx.font = "10px sans-serif";
  ctx.fillText("日K（蜡烛图）", pad.l, 12);

  visible.forEach((d, i) => {
    const x = pad.l + i * (plotW / visible.length) + candleW / 2;
    const up = d.close >= d.open;
    const color = up ? "#16a34a" : "#dc2626";

    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, y(d.high));
    ctx.lineTo(x, y(d.low));
    ctx.stroke();

    const top = y(Math.max(d.open, d.close));
    const bot = y(Math.min(d.open, d.close));
    const bodyH = Math.max(1, bot - top);
    ctx.fillRect(x - candleW / 2, top, candleW, bodyH);
  });
}

function CandleChart({ ohlc }: { ohlc: HomeCard["ohlc"] }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (ref.current) drawCandles(ref.current, ohlc);
  }, [ohlc]);

  return <canvas ref={ref} className="candle-chart" width={340} height={160} />;
}

export default function HomePage() {
  const { navigate } = useOutletContext<LayoutContextValue>();
  const [cards, setCards] = useState<HomeCard[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    api.home()
      .then(setCards)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const onRefresh = (e: Event) => {
      const ev = e as CustomEvent<string>;
      if (ev.detail === "/") load();
    };
    window.addEventListener("page-refresh", onRefresh);
    return () => window.removeEventListener("page-refresh", onRefresh);
  }, [load]);

  const enterAnalysis = (code: string) => {
    localStorage.setItem("underlying", code);
    window.dispatchEvent(new CustomEvent("underlying-change", { detail: code }));
    navigate("/heatmap");
  };

  if (error) return <p className="muted">加载失败：{error}</p>;

  return (
    <>
      <p className="muted" style={{ marginTop: 0 }}>
        同时展示所有可交易 ETF 标的的现价与蜡烛图，点击卡片进入期权分析
      </p>
      {!cards.length ? (
        <p className="muted">加载中…</p>
      ) : (
        <div className="home-grid">
          {cards.map((card) => {
            const chgCls = card.change_pct >= 0 ? "up" : "down";
            const chgSign = card.change_pct >= 0 ? "+" : "";
            return (
              <div key={card.code} className="etf-card">
                <div className="etf-head">
                  <div>
                    <strong>{card.code} {card.name}</strong>
                    <div className="muted">
                      HV20 {card.hv20 != null ? `${card.hv20.toFixed(1)}%` : "—"}
                      {card.spot_source ? ` · ${sourceLabel(card.spot_source)}` : ""}
                      {card.ohlc_source ? ` · ${ohlcLabel(card.ohlc_source)}` : ""}
                    </div>
                  </div>
                  <div>
                    <div className="etf-price">{card.spot.toFixed(3)}</div>
                    <div className={chgCls}>{chgSign}{card.change_pct.toFixed(2)}%</div>
                  </div>
                </div>
                <CandleChart ohlc={card.ohlc} />
                <button
                  className="btn btn-primary"
                  style={{ marginTop: 12, width: "100%" }}
                  onClick={() => enterAnalysis(card.code)}
                >
                  进入分析 →
                </button>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
