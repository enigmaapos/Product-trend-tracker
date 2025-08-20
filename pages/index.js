// pages/index.js
import { useEffect, useState } from "react";

export default function Home() {
  const [products, setProducts] = useState([]);

  useEffect(() => {
    fetch("/api/trending")
      .then(res => res.json())
      .then(setProducts);
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold">TikTok Trending Products</h1>
      <table className="mt-4 w-full border">
        <thead>
          <tr>
            <th>Product</th>
            <th>24h Change %</th>
            <th>Z-Score</th>
            <th>Signal</th>
          </tr>
        </thead>
        <tbody>
          {products.map(p => (
            <tr key={p.product_id}>
              <td>{p.product_id}</td>
              <td>{(p.change_pct * 100).toFixed(2)}%</td>
              <td>{p.z_score.toFixed(2)}</td>
              <td className={p.signal === "BREAKOUT" ? "text-red-500" : "text-green-500"}>
                {p.signal}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
