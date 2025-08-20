# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import datetime
from typing import Optional, Dict

# Create a FastAPI instance
app = FastAPI(title="Trending Products API")

# Configure CORS to allow the frontend to access the API
# The previous list of origins was too specific. We will use a wildcard
# to allow requests from any origin, which is suitable for testing.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def detect_trending_products(
    df: pd.DataFrame,
    freq='1H',
    now=None,
    min_hours=30,  # need at least 30 hours to get 24h + prev24h windows
    weights=None
):
    """
    Detect trending products via Binance-style 24h change logic.

    Required columns:
      product_id (str), ts (datetime64), price (float), units_sold (int/float)
    Optional columns:
      views (float), likes (float), add_to_cart (float)

    Returns a DataFrame with the latest snapshot per product including:
      24h window metrics, % changes vs prev 24h, z-scores, TrendScore, signal
    """

    req_cols = {'product_id','ts','price','units_sold'}
    missing = req_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Ensure dtypes
    df = df.copy()
    df['ts'] = pd.to_datetime(df['ts'])
    if now is None:
        now = df['ts'].max()

    # Resample to hourly per product for stability
    metrics = ['units_sold','views','likes','add_to_cart']
    for col in metrics:
        if col not in df.columns:
            df[col] = 0.0

    # Build a complete hourly index per product
    df = (
        df.set_index('ts')
          .groupby('product_id', group_keys=False)
          .apply(lambda g: g.resample(freq).agg({
              'price':'last',
              'units_sold':'sum',
              'views':'sum',
              'likes':'sum',
              'add_to_cart':'sum'
          }))
          .reset_index()
    )

    # Forward-fill price within each product
    df['price'] = df.groupby('product_id')['price'].ffill()

    # Drop products with insufficient history
    spans = df.groupby('product_id')['ts'].agg(['min','max'])
    long_enough = spans[(spans['max'] - spans['min']) >= pd.Timedelta(hours=min_hours)].index
    df = df[df['product_id'].isin(long_enough)]

    # Rolling 24h sums
    def roll24(g):
        g = g.sort_values('ts')
        g['units_24h'] = g['units_sold'].rolling('24H', on='ts').sum()
        g['views_24h'] = g['views'].rolling('24H', on='ts').sum()
        g['likes_24h'] = g['likes'].rolling('24H', on='ts').sum()
        g['atc_24h']   = g['add_to_cart'].rolling('24H', on='ts').sum()
        g['gmv_24h']   = (g['price']*g['units_sold']).rolling('24H', on='ts').sum()
        # 24h ago price: last observed price <= ts-24h
        g['price_24h_ago'] = g['price'].shift(24)  # hourly resample → 24 steps
        return g

    df = df.groupby('product_id', group_keys=False).apply(roll24)

    # Previous 24h sums (shift by 24 hourly steps)
    for c in ['units_24h','views_24h','likes_24h','atc_24h','gmv_24h']:
        df[f'{c}_prev'] = df.groupby('product_id')[c].shift(24)

    # 24h % changes
    def pct_change(cur, prev):
        return np.where(prev > 0, (cur - prev)/prev, np.nan)

    df['d_units_24h_pct'] = pct_change(df['units_24h'], df['units_24h_prev'])
    df['d_views_24h_pct'] = pct_change(df['views_24h'], df['views_24h_prev'])
    df['d_likes_24h_pct'] = pct_change(df['likes_24h'], df['likes_24h_prev'])
    df['d_atc_24h_pct']   = pct_change(df['atc_24h'],   df['atc_24h_prev'])
    df['d_gmv_24h_pct']   = pct_change(df['gmv_24h'],   df['gmv_24h_prev'])
    df['d_price_24h_pct'] = pct_change(df['price'],     df['price_24h_ago'])

    # 7-day median baseline for velocity (need resample to daily windows of 24h sums)
    def add_velocity(g):
        g = g.sort_values('ts')
        # daily 24h sums via 24-hour rolling already exist; take per-hour point and compare with 7d median
        med_units_7d = g['units_24h'].rolling('7D', on='ts').median()
        g['units_velocity'] = np.where(med_units_7d > 0, g['units_24h'] / med_units_7d, np.nan)
        return g

    df = df.groupby('product_id', group_keys=False).apply(add_velocity)

    # Hourly momentum history for persistence check
    df['units_1h_change'] = df.groupby('product_id')['units_sold'].pct_change()

    # Take latest snapshot per product (closest hour ≤ now)
    latest_idx = df.groupby('product_id')['ts'].idxmax()
    snap = df.loc[latest_idx].copy()

    # Z-scores across products (robust: handle nan/std=0)
    z_cols = ['d_units_24h_pct','d_views_24h_pct','d_gmv_24h_pct','d_likes_24h_pct','d_atc_24h_pct','d_price_24h_pct']
    for c in z_cols:
        x = snap[c]
        mu = np.nanmean(x)
        sd = np.nanstd(x, ddof=0)
        if not np.isfinite(sd) or sd == 0:
            snap[f'z_{c}'] = 0.0
        else:
            snap[f'z_{c}'] = (x - mu) / sd

    # Composite TrendScore (reweight if some are missing)
    default_weights = {
        'z_d_units_24h_pct': 0.35,
        'z_d_views_24h_pct': 0.25,
        'z_d_gmv_24h_pct':   0.20,
        'z_d_likes_24h_pct': 0.10,
        'z_d_atc_24h_pct':   0.10,
    }
    if weights is not None:
        default_weights.update(weights)

    # Normalize weights to 1.0 for available features
    available = {k:v for k,v in default_weights.items() if k in snap.columns}
    s = sum(available.values())
    available = {k:v/s for k,v in available.items()} if s > 0 else {k:0 for k in default_weights}

    snap['TrendScore'] = 0.0
    for k, w in available.items():
        snap['TrendScore'] += w * snap[k]

    # Persistence: count positive units_1h_change in last 6 hours
    def last6_pos(g):
        g = g.sort_values('ts')
        sub = g.tail(6)
        return np.nansum((sub['units_1h_change'] > 0).astype(int))

    pos6 = df.groupby('product_id').apply(last6_pos)
    snap = snap.merge(pos6.rename('pos_hours_last6'), on='product_id', how='left')

    # Signal rules
    def decide(row):
        breakout = (
            (row['d_units_24h_pct'] is not np.nan) and
            (row['d_units_24h_pct'] >= 1.50) and
            (row['z_d_units_24h_pct'] >= 2.0) and
            (row.get('units_velocity', np.nan) >= 2.0)
        )
        momentum = (
            (row['TrendScore'] >= 1.5) and
            (row.get('pos_hours_last6', 0) >= 3)
        )
        discount_spike = (
            (row['d_price_24h_pct'] <= -0.10) and
            (row['d_units_24h_pct'] >= 0.50)
        )
        cooling = (
            (row['TrendScore'] < 0.5) or
            (row['d_units_24h_pct'] <= 0)
        )

        if breakout:
            return 'BREAKOUT'
        if momentum:
            return 'MOMENTUM'
        if discount_spike:
            return 'DISCOUNT_SPIKE'
        if cooling:
            return 'COOLING'
        return 'STEADY'

    snap['signal'] = snap.apply(decide, axis=1)

    # Useful output columns
    out_cols = [
        'product_id','ts','price','units_24h','gmv_24h','views_24h','likes_24h','atc_24h',
        'd_units_24h_pct','d_gmv_24h_pct','d_views_24h_pct','d_likes_24h_pct','d_atc_24h_pct','d_price_24h_pct',
        'z_d_units_24h_pct','z_d_gmv_24h_pct','z_d_views_24h_pct','z_d_likes_24h_pct','z_d_atc_24h_pct',
        'units_velocity','TrendScore','pos_hours_last6','signal'
    ]
    existing = [c for c in out_cols if c in snap.columns]
    return snap[existing].sort_values(['signal','TrendScore'], ascending=[True, False])


def get_mock_tiktok_data():
    """
    This function simulates fetching data from a TikTok API.
    
    In a real application, you would replace this with actual API calls to
    the TikTok for Business API, handling authentication and data retrieval.
    """
    products = ['A101', 'B202', 'C303', 'D404', 'E505']
    data = []
    now = datetime.datetime.now(datetime.timezone.utc)
    
    for product_id in products:
        for i in range(48, 0, -1):  # Generate data for the last 48 hours
            ts = now - datetime.timedelta(hours=i)
            
            units_sold = np.random.randint(5, 50)
            views = np.random.randint(20, 200)
            likes = np.random.randint(5, 30)
            add_to_cart = np.random.randint(1, 10)
            price = np.random.uniform(20.0, 100.0)
            
            # Simulate a recent trend for product B202
            if product_id == 'B202' and i <= 24: # Last 24 hours
                units_sold = np.random.randint(50, 200)
                views = np.random.randint(500, 2000)
                likes = np.random.randint(100, 300)
                add_to_cart = np.random.randint(20, 50)
            
            data.append({
                'product_id': product_id,
                'ts': ts,
                'price': price,
                'units_sold': units_sold,
                'views': views,
                'likes': likes,
                'add_to_cart': add_to_cart
            })
    
    return pd.DataFrame(data)

@app.get("/trending-products")
async def get_trending_products():
    """
    API endpoint to get the list of trending products.
    """
    try:
        # Step 1: Fetch data (mock or real)
        # You would replace this with real API calls
        df = get_mock_tiktok_data()
        
        # Step 2: Run the trending detection algorithm
        trending_df = detect_trending_products(df)
        
        # Step 3: Convert the DataFrame to a JSON-serializable format
        # Use records to get a list of dictionaries, one for each row
        results = trending_df.to_dict(orient='records')
        
        return results
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

