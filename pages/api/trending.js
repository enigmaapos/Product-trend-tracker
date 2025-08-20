// pages/api/trending.js
import { mean, std } from "mathjs";

export default function handler(req, res) {
  // Example incoming product data
  // In production, you’d pull from TikTok Shop API, Supabase, or CSV
  const data = [
    { product_id: "A1", price: 20, units_24h: 120, units_prev24h: 50 },
    { product_id: "B2", price: 35, units_24h: 30, units_prev24h: 25 },
    { product_id: "C3", price: 15, units_24h: 10, units_prev24h: 10 },
  ];

  // Compute percentage change
  data.forEach(p => {
    if (p.units_prev24h > 0) {
      p.change_pct = (p.units_24h - p.units_prev24h) / p.units_prev24h;
    } else {
      p.change_pct = null;
    }
  });

  // Z-score normalize across products
  const changes = data.map(p => p.change_pct || 0);
  const mu = mean(changes);
  const sigma = std(changes) || 1;
  data.forEach(p => {
    p.z_score = ((p.change_pct || 0) - mu) / sigma;
  });

  // Classify signals
  data.forEach(p => {
    if (p.change_pct >= 1.5 && p.z_score >= 2) {
      p.signal = "BREAKOUT";
    } else if (p.z_score >= 1) {
      p.signal = "MOMENTUM";
    } else {
      p.signal = "STEADY";
    }
  });

  res.status(200).json(data);
}
