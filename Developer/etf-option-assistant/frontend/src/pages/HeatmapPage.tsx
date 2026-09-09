import TradeDrawer from "../components/TradeDrawer";
import { useTrade } from "../context/TradeContext";
import type { HeatmapCell, HeatmapResponse } from "../types";

function heatColor(iv: number, vmin: number, vmax: number) {
  const t = Math.max(0, Math.min(1, (iv - vmin) / (vmax - vmin || 1)));
  const r = Math.round(254 - t * 154);
  const g = Math.round(242 - t * 192);
  return `rgb(${r},${g},${g})`;
}

function cellMap(data: HeatmapResponse) {
  const map = new Map<string, HeatmapCell>();
  data.cells.forEach((c) => map.set(`${c.month.short_label}_${c.strike}_${c.is_call}`, c));
  return map;
}

function strikeLabel(strike: number, isCall: boolean, isNonStandard: boolean) {
  const side = isCall ? "购" : "沽";
  const adj = isNonStandard ? "调" : "";
  return `${strike.toFixed(2)}${adj}${side}`;
}

export default function HeatmapPage({ data }: { data: HeatmapResponse }) {
  const { getCellState, toggleCell } = useTrade();
  const map = cellMap(data);
  const midRow = Math.floor(data.months.length / 2);
  const putNonStd = new Set(data.put_non_standard ?? []);
  const callNonStd = new Set(data.call_non_standard ?? []);

  const colorLegend = data.iv_color_source === "hv_percentile"
    ? ` · IV色阶: ${data.hv_trading_days ?? "10年"}日20日HV 20%(${data.vmin.toFixed(1)}%)→80%(${data.vmax.toFixed(1)}%)`
    : data.iv_color_source === "mock"
      ? ` · IV色阶: 模拟HV 20%(${data.vmin.toFixed(1)}%)→80%(${data.vmax.toFixed(1)}%)`
      : ` · IV色阶: 当前链 ${data.vmin.toFixed(1)}%–${data.vmax.toFixed(1)}%`;

  const renderCell = (
    cell: HeatmapCell | undefined,
    strike: number,
    month: HeatmapCell["month"],
    isCall: boolean,
    isNonStandard: boolean,
  ) => {
    if (!cell || cell.iv == null) {
      return <div className={`heat-cell empty${isNonStandard ? " heat-cell-adj" : ""}`}>--</div>;
    }
    const state = getCellState(cell.state_key);
    const iv = cell.iv;

    return (
      <div
        className={`heat-cell${isNonStandard ? " heat-cell-adj" : ""} ${state || ""}`}
        style={{ background: heatColor(iv, data.vmin, data.vmax) }}
        title={cell.code && !cell.is_standard ? cell.code : undefined}
        onClick={() => toggleCell({
          key: cell.state_key,
          code: cell.code || `${data.underlying}${isCall ? "购" : "沽"}${month.short_label}${String(strike).replace(".", "")}`,
          strike,
          month: month.short_label,
          isCall,
          iv: cell.iv,
          delta: cell.delta ?? 0,
          gamma: cell.gamma ?? 0,
          theta: cell.theta ?? 0,
          vega: cell.vega ?? 0,
          bid: cell.bid,
          ask: cell.ask,
        })}
      >
        <div><strong>IV ({iv.toFixed(1)}%)</strong></div>
        <div>Δ {(cell.delta ?? 0).toFixed(3)}</div>
      </div>
    );
  };

  return (
    <div className="page-split active">
      <div className="split-quote-pane">
        <div className="legend-row">
          <span className="muted">
            {data.underlying} · 现价 {data.spot.toFixed(3)} · 行权价±20% · 间距 {data.strike_step}
            {data.hv20 != null ? ` · HV20 ${data.hv20.toFixed(1)}%` : ""}
            {colorLegend}
            {data.include_non_standard ? " · 含非标准合约（独立行权价列）" : ""}
            · 更新 {new Date(data.updated_at).toLocaleTimeString("zh-CN")}
          </span>
        </div>
        <div className="heatmap-wrap">
          <table className="heatmap-table">
            <thead>
              <tr>
                <th className="col-month" />
                {data.put_strikes.map((k) => (
                  <th
                    key={`p${k}`}
                    className={`col-strike strike-put${putNonStd.has(k) ? " strike-adj" : ""}`}
                    title={putNonStd.has(k) ? "非标准（除权调整）合约行权价" : undefined}
                  >
                    {strikeLabel(k, false, putNonStd.has(k))}
                  </th>
                ))}
                <th className="col-spot spot-col"><span className="spot-head">现价</span></th>
                {data.call_strikes.map((k) => (
                  <th
                    key={`c${k}`}
                    className={`col-strike strike-call${callNonStd.has(k) ? " strike-adj" : ""}`}
                    title={callNonStd.has(k) ? "非标准（除权调整）合约行权价" : undefined}
                  >
                    {strikeLabel(k, true, callNonStd.has(k))}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.months.map((month, mi) => (
                <tr key={month.label}>
                  <th className="col-month" title={month.label}>{month.short_label}</th>
                  {data.put_strikes.map((strike) => (
                    <td key={`p${strike}`} className="col-strike">
                      {renderCell(
                        map.get(`${month.short_label}_${strike}_false`),
                        strike,
                        month,
                        false,
                        putNonStd.has(strike),
                      )}
                    </td>
                  ))}
                  <td className="col-spot spot-col">
                    <div className="spot-line" />
                    {mi === midRow && <div className="spot-label">{data.spot.toFixed(3)}</div>}
                  </td>
                  {data.call_strikes.map((strike) => (
                    <td key={`c${strike}`} className="col-strike">
                      {renderCell(
                        map.get(`${month.short_label}_${strike}_true`),
                        strike,
                        month,
                        true,
                        callNonStd.has(strike),
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="note">
          * IV、Greeks 均以中间价 Mid = (买一 + 卖一) / 2 计算
          {data.include_non_standard ? "；表头带「调」为除权调整合约的独立行权价列" : ""}
        </div>
      </div>
      <div className="split-trade-pane">
        <TradeDrawer />
      </div>
    </div>
  );
}
