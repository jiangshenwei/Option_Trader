import TradeDrawer from "../components/TradeDrawer";
import { useTrade } from "../context/TradeContext";
import type { MonthInfo, OptionQuote, TQuoteResponse, TQuoteRow } from "../types";

interface TQuotePageProps {
  data: TQuoteResponse;
  months: MonthInfo[];
  monthIdx: number;
  onMonthChange: (idx: number) => void;
}

function stateKey(strike: number, month: string, isCall: boolean, quote?: OptionQuote | null) {
  const side = isCall ? "C" : "P";
  if (quote && quote.is_standard === false) {
    return `${side}_adj_${quote.code}_${month}_${strike}`;
  }
  return `${side}_${strike}_${month}`;
}

function buildMeta(
  row: TQuoteRow,
  quote: OptionQuote,
  data: TQuoteResponse,
  isCall: boolean,
) {
  const month = data.month.short_label;
  return {
    key: stateKey(row.strike, month, isCall, quote),
    code: quote.code,
    strike: row.strike,
    month,
    isCall,
    iv: quote.iv,
    delta: quote.greeks.delta,
    gamma: quote.greeks.gamma,
    theta: quote.greeks.theta,
    vega: quote.greeks.vega,
    bid: quote.bid,
    ask: quote.ask,
  };
}

function fmt(v: number | null | undefined, digits = 3) {
  return v != null ? v.toFixed(digits) : "—";
}

export default function TQuotePage({ data, months, monthIdx, onMonthChange }: TQuotePageProps) {
  const { getCellState, toggleCell } = useTrade();
  const updated = new Date(data.updated_at).toLocaleTimeString("zh-CN");

  const renderSide = (row: TQuoteRow, quote: OptionQuote | null, isCall: boolean) => {
    if (!quote) return null;
    const key = stateKey(row.strike, data.month.short_label, isCall, quote);
    const state = getCellState(key);
    const cls = `tquote-clickable${state ? ` tquote-${state}` : ""}`;
    const meta = buildMeta(row, quote, data, isCall);
    const onClick = () => toggleCell(meta);
    const title = quote.name || (row.is_standard === false ? `${quote.code} · 非标准` : undefined);

    return (
      <>
        <td className={cls} onClick={onClick} title={title}>{fmt(quote.bid)}</td>
        <td className={cls} onClick={onClick} title={title}>{fmt(quote.ask)}</td>
        <td className={cls} onClick={onClick} title={title}>{fmt(quote.iv, 1)}</td>
        <td className={cls} onClick={onClick} title={title}>{fmt(quote.greeks.delta)}</td>
        <td className={cls} onClick={onClick} title={title}>{fmt(quote.greeks.gamma, 2)}</td>
        <td className={cls} onClick={onClick} title={title}>{fmt(quote.greeks.theta, 1)}</td>
        <td className={cls} onClick={onClick} title={title}>{fmt(quote.greeks.vega, 1)}</td>
      </>
    );
  };

  return (
    <div className="page-split active">
      <div className="split-quote-pane">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <p className="muted split-intro" style={{ margin: 0 }}>
            T 型报价 — {data.month.label} · 点击购/沽侧三态点选 · 更新 {updated}
            {data.include_non_standard ? " · 含非标准合约（独立行权价行）" : ""}
          </p>
          <div className="month-tabs">
            {months.map((m, i) => (
              <button
                key={m.label}
                type="button"
                className={`month-tab${i === monthIdx ? " active" : ""}`}
                title={m.label}
                onClick={() => onMonthChange(i)}
              >
                {m.short_label}
              </button>
            ))}
          </div>
        </div>
        <div className="tquote-scroll">
          <table className="data-table tquote-table">
            <thead>
              <tr>
                <th>C买</th><th>C卖</th><th>CIV</th><th>CΔ</th><th>CΓ</th><th>CΘ</th><th>CV</th>
                <th>K</th>
                <th>P买</th><th>P卖</th><th>PIV</th><th>PΔ</th><th>PΓ</th><th>PΘ</th><th>PV</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr
                  key={row.strike}
                  className={row.is_standard === false ? "tquote-adjusted" : undefined}
                >
                  {row.call ? renderSide(row, row.call, true) : (
                    <td colSpan={7} className="muted">—</td>
                  )}
                  <td>
                    <strong>{row.strike.toFixed(2)}</strong>
                    {row.is_standard === false && (
                      <span className="heat-badge-adj inline" title="非标准（除权调整）合约行权价">调</span>
                    )}
                  </td>
                  {row.put ? renderSide(row, row.put, false) : (
                    <td colSpan={7} className="muted">—</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="note">
          所有 IV、Delta、Gamma、Theta、Vega 均基于中间价反解/计算
          {data.include_non_standard ? "；灰色行权价行为除权调整合约" : ""}
        </div>
      </div>
      <div className="split-trade-pane">
        <TradeDrawer />
      </div>
    </div>
  );
}
