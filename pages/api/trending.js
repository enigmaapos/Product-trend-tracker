
// pages/api/trending.js

// --- Simple math helpers ---
function mean(arr) {
  if (!arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function std(arr) {
  if (!arr.length) return 0;
  const mu = mean(arr);
  const variance = mean(arr.map(x => (x - mu) ** 2));
  return Math.sqrt(variance);
}

export default function handler(req, res) {
  // Support GET (demo data) and POST (custom products)
  let data;
  if (req.method === "POST" && req.body?.products) {
    data = req.body.products;
  } else {
    data = [
      { product_id: "A1", price: 20, units_24h: 120, units_prev24h: 50 },
      { product_id: "B2", price: 35, units_24h: 30, units_prev24h: 25 },
      { product_id: "C3", price: 15, units_24h: 10, units_prev24h: 10 },
      { product_id: "D4", price: 40, units_24h: 5, units_prev24h: 15 },
    ];
  }

  // --- Compute metrics ---
  data.forEach((p) => {
    if (p.units_prev24h && p.units_prev24h > 0) {
      p.change_pct = (p.units_24h - p.units_prev24h) / p.units_prev24h;
    } else {
      p.change_pct = 0; // Prevent NaN
    }

    // Sales growth ratio
    p.sales_growth = p.units_24h - p.units_prev24h;
  });

  // --- Normalize with Z-score ---
  const changes = data.map((p) => p.change_pct);
  const mu = mean(changes);
  const sigma = std(changes) || 1;

  data.forEach((p) => {
    p.z_score = (p.change_pct - mu) / sigma;
  });

  // --- Classify signals ---
  data.forEach((p) => {
    if (p.change_pct >= 1.5 && p.z_score >= 2) {
      p.signal = "🚀 BREAKOUT";
    } else if (p.change_pct > 0.3 && p.z_score >= 1) {
      p.signal = "🔥 MOMENTUM";
    } else if (p.change_pct < -0.3 && p.z_score <= -1) {
      p.signal = "📉 DECLINE";
    } else {
      p.signal = "STEADY";
    }
  });

  // --- Sort & trim results ---
  data.sort((a, b) => b.z_score - a.z_score);
  const topProducts = data.slice(0, 10);

  // --- Response ---
  res.status(200).json({
    timestamp: new Date().toISOString(),
    count: topProducts.length,
    products: topProducts,
  });
}
