import { useEffect, useState } from "react";

export default function Home() {
  const [products, setProducts] = useState([]); // ✅ trending products
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null); // ✅ track errors

  useEffect(() => {
    async function fetchTrending() {
      try {
        const res = await fetch("/api/trending");

        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }

        const data = await res.json();

        // ✅ Ensure it's always an array
        if (Array.isArray(data)) {
          setProducts(data);
        } else {
          setProducts([]);
        }
      } catch (err) {
        console.error("Error fetching trending products:", err);
        setError("Failed to load trending products.");
        setProducts([]);
      } finally {
        setLoading(false);
      }
    }

    fetchTrending();
  }, []);

  // ✅ Loading state
  if (loading) {
    return <p className="text-center text-gray-500">⏳ Loading trending products...</p>;
  }

  // ✅ Error state
  if (error) {
    return <p className="text-center text-red-500">{error}</p>;
  }

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">📈 Trending Products</h1>

      {products.length === 0 ? (
        <p className="text-gray-500">⚠️ No trending products found.</p>
      ) : (
        <ul className="space-y-2">
          {products.map((p) => (
            <li
              key={p.product_id}
              className="p-4 border rounded-lg shadow-sm flex justify-between items-center hover:bg-gray-50 transition"
            >
              <span>
                <strong>{p.product_id}</strong> — ${p.price}
              </span>
              <span
                className={`text-sm font-medium px-2 py-1 rounded ${
                  p.signal === "bullish"
                    ? "bg-green-100 text-green-700"
                    : p.signal === "bearish"
                    ? "bg-red-100 text-red-700"
                    : "bg-gray-100 text-gray-600"
                }`}
              >
                {p.signal || "neutral"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
