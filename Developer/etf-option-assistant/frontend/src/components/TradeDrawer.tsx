import { useNavigate } from "react-router-dom";
import { useTrade } from "../context/TradeContext";
import type { TradeLeg } from "../types";

function orderPrice(item: TradeLeg) {
  const bid = item.bid ?? 0.08;
  const ask = item.ask ?? 0.085;
  if (item.quoteType === "opponent") return item.direction === "long" ? ask : bid;
  if (item.quoteType === "limit") return item.direction === "long" ? bid : ask;
  return (bid + ask) / 2;
}

export default function TradeDrawer({ fullPage = false }: { fullPage?: boolean }) {
  const { tradeList, updateLeg, removeLeg } = useTrade();
  const navigate = useNavigate();

  let sumD = 0, sumG = 0, sumT = 0, sumV = 0, sumPrem = 0;
  tradeList.forEach((item) => {
    const price = orderPrice(item);
    const sign = item.direction === "long" ? 1 : -1;
    sumD += item.delta * sign * item.qty;
    sumG += item.gamma * sign * item.qty;
    sumT += item.theta * sign * item.qty;
    sumV += item.vega * sign * item.qty;
    sumPrem += price * item.qty * 10000 * (item.direction === "long" ? -1 : 1);
  });

  const summary = `交易列表 (${tradeList.length}) · ΣΔ ${sumD.toFixed(2)} · ΣΓ ${sumG.toFixed(2)} · ΣΘ ${sumT.toFixed(1)} · ΣV ${sumV.toFixed(1)} · 预估权利金 ¥${Math.abs(sumPrem).toLocaleString()}`;

  const copyOrders = () => {
    if (!tradeList.length) return alert("交易列表为空");
    const text = tradeList.map((t) => {
      const action = t.direction === "long" ? "买入" : "卖出";
      return `${action} ${t.code} 数量${t.qty}张 委托价${orderPrice(t).toFixed(4)}`;
    }).join("\n");
    navigator.clipboard?.writeText(text).then(() => alert("已复制"));
  };

  return (
    <div className="trade-drawer">
      <div className="trade-drawer-head">
        <strong>{summary}</strong>
        <div className="trade-drawer-actions">
          <button className="btn btn-sm" onClick={copyOrders}>复制下单信息</button>
          {!fullPage && (
            <button className="btn btn-sm btn-link" onClick={() => navigate("/tradelist")}>查看完整列表 →</button>
          )}
          <button className="btn btn-sm btn-disabled" disabled title="Phase 2">一键下单</button>
        </div>
      </div>
      <div className="trade-table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>合约</th><th>方向</th><th>报价方式</th><th>数量</th><th>委托价</th>
              <th>IV</th><th>Δ</th><th>Γ</th><th>Θ</th><th>V</th><th>权利金</th><th></th>
            </tr>
          </thead>
          <tbody>
            {tradeList.length === 0 ? (
              <tr><td colSpan={12} className="muted">点击热力图或 T 型报价格子添加合约</td></tr>
            ) : tradeList.map((item, i) => {
              const price = orderPrice(item);
              const dirCls = item.direction === "long" ? "up" : "down";
              return (
                <tr key={item.key}>
                  <td>{item.code}</td>
                  <td className={dirCls}><strong>{item.direction === "long" ? "做多" : "做空"}</strong></td>
                  <td>
                    <select value={item.quoteType} onChange={(e) => updateLeg(i, { quoteType: e.target.value as TradeLeg["quoteType"] })}>
                      <option value="mid">中间价</option>
                      <option value="opponent">对手价</option>
                      <option value="limit">挂单价</option>
                    </select>
                  </td>
                  <td><input type="number" min={1} value={item.qty} onChange={(e) => updateLeg(i, { qty: +e.target.value })} style={{ width: 60 }} /></td>
                  <td title={`买一 ${item.bid?.toFixed(4) ?? "—"} / 卖一 ${item.ask?.toFixed(4) ?? "—"}`}>
                    {price.toFixed(4)}
                  </td>
                  <td>{item.iv?.toFixed(1)}%</td>
                  <td>{item.delta.toFixed(3)}</td>
                  <td>{item.gamma.toFixed(2)}</td>
                  <td>{item.theta.toFixed(1)}</td>
                  <td>{item.vega.toFixed(1)}</td>
                  <td>¥{(price * item.qty * 10000).toLocaleString()}</td>
                  <td><button className="btn" onClick={() => removeLeg(i)}>删除</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
