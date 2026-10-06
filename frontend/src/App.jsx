import { useEffect, useState } from "react";
 
const sampleTrade = () => ({
  symbol: "ABCD",
  side: Math.random() < 0.5 ? "BUY" : "SELL",
  quantity: Math.ceil(Math.random() * 500),
  price: +(130 + Math.random() * 5).toFixed(2),
});
 
function TradeTable({ title, trades }) {
  return (
    <div style={{ flex: 1 }}>
      <h2>{title} ({trades.length})</h2>
      <table border="1" cellPadding="4" style={{ borderCollapse: "collapse" }}>
        <thead><tr><th>Seq</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Price</th></tr></thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.trade_id}>
              <td>{t.seq_no}</td><td>{t.symbol}</td><td>{t.side}</td>
              <td>{t.quantity}</td><td>{t.price}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
 
export default function App() {
  const [legacy, setLegacy] = useState([]);
  const [cloud, setCloud] = useState([]);
 
  const load = async () => {
    setLegacy(await (await fetch("/legacy/trades")).json());
    setCloud((await (await fetch("/api/v1/trades")).json()).trades);
  };
  useEffect(() => { load(); }, []);
 
  const add = async (url) => {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sampleTrade()),
    });
    load();
  };
 
  return (
    <div style={{ fontFamily: "sans-serif", padding: 16 }}>
      <h1>transitionx: basic setup check</h1>
      <button onClick={() => add("/legacy/trades")}>Add trade to LEGACY</button>{" "}
      <button onClick={() => add("/api/v1/trades")}>Add trade to CLOUD</button>{" "}
      <button onClick={load}>Refresh</button>
      <div style={{ display: "flex", gap: 24, marginTop: 16 }}>
        <TradeTable title="Legacy system" trades={legacy} />
        <TradeTable title="Cloud system" trades={cloud} />
      </div>
    </div>
  );
}
