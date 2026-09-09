import TradeDrawer from "../components/TradeDrawer";

export default function TradeListPage() {
  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      <TradeDrawer fullPage />
      <div className="note">委托价按报价方式计算；IV/Greeks 展示值基于中间价</div>
    </div>
  );
}
