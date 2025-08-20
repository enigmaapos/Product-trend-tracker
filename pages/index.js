import { useEffect, useState } from "react";

export default function Home() {
  const [products, setProducts] = useState([]); // ✅ start with empty array
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchTrending() {
      try {
        const res = await fetch("/api/trending");
        const data = await res.json();

        // ✅ Ensure it's always an array
        if (Array.isArray(data)) {
          setProducts(data);
        } else {
          setProducts([]);
        }
      } catch (err) {
        console.error("Error fetching trending products:", err);
        setProducts([]);
      } finally {
        setLoading(false);
      }
    }

    fetchTrending();
  }, []);

  if (loading) return <p className="text-center">Loading...</p>;

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">📈 Trending Products</h1>
      {products.length === 0 ? (
        <p>No trending products found</p>
      ) : (
        <ul className="space-y-2">
          {products.map((p) => (
            <li
              key={p.product_id}
              className="p-4 border rounded-lg shadow-sm flex justify-between"
            >
              <span>
                <strong>{p.product_id}</strong> — ${p.price}
              </span>
              <span className="text-sm text-gray-600">{p.signal}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
