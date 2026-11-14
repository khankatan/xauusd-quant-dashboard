import numpy as np
import pandas as pd
from engine.config import ATR_LEN, VWRSI_LEN, H1_EMA_LEN

def compute_all_features(df):
    df = df.copy()
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.sort_values("datetime").reset_index(drop=True)

    thai_dt = df["datetime"] + pd.Timedelta(hours=7)
    df["thai_date"] = thai_dt.dt.date
    df["thai_hour"] = thai_dt.dt.hour
    df["thai_minute"] = thai_dt.dt.minute
    df["thai_mins"] = df["thai_hour"] * 60 + df["thai_minute"]

    # 1. Multi-Timeframe H1 & H4 Trend (ใช้ merge_asof ป้องกัน MergeError และ Zero Look-Ahead)
    df_indexed = df.set_index("datetime")

    df_h1 = df_indexed.resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna().reset_index()
    df_h1["h1_ema"] = df_h1["close"].ewm(span=H1_EMA_LEN, adjust=False).mean()
    # เลื่อนเวลาไป 1 ชั่วโมงเต็ม เพื่อให้ M15 อ่านเฉพาะแท่ง H1 ที่ปิดสมบูรณ์แล้วเท่านั้น
    df_h1["valid_from"] = df_h1["datetime"] + pd.Timedelta(hours=1)
    df_h1 = df_h1[["valid_from", "close", "h1_ema"]].rename(columns={"close": "h1_close"}).sort_values("valid_from")

    df_h4 = df_indexed.resample("4h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna().reset_index()
    df_h4["h4_ema"] = df_h4["close"].ewm(span=21, adjust=False).mean()
    df_h4["valid_from"] = df_h4["datetime"] + pd.Timedelta(hours=4)
    df_h4 = df_h4[["valid_from", "close", "h4_ema"]].rename(columns={"close": "h4_close"}).sort_values("valid_from")

    df = pd.merge_asof(df, df_h1, left_on="datetime", right_on="valid_from", direction="backward").drop(columns=["valid_from"])
    df = pd.merge_asof(df, df_h4, left_on="datetime", right_on="valid_from", direction="backward").drop(columns=["valid_from"])

    # 2. Synthetic Volume & Session VWAP รายวัน
    df["tick_vol"] = (df["high"] - df["low"]).replace(0, 0.01)
    df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3.0
    df["pv"] = df["typical_price"] * df["tick_vol"]
    df["cum_pv"] = df.groupby("thai_date")["pv"].cumsum()
    df["cum_vol"] = df.groupby("thai_date")["tick_vol"].cumsum()
    df["vwap"] = df["cum_pv"] / df["cum_vol"]

    df["vwap_diff_sq"] = ((df["typical_price"] - df["vwap"]) ** 2) * df["tick_vol"]
    df["vwap_std"] = np.sqrt(df.groupby("thai_date")["vwap_diff_sq"].cumsum() / df["cum_vol"])
    df["vwap_upper"] = df["vwap"] + (1.25 * df["vwap_std"])
    df["vwap_lower"] = df["vwap"] - (1.25 * df["vwap_std"])

    # 3. Volume-Weighted RSI (VWRSI 14)
    delta = df["close"].diff()
    up_vol = delta.clip(lower=0) * df["tick_vol"]
    down_vol = (-delta.clip(upper=0)) * df["tick_vol"]
    avg_up = up_vol.ewm(alpha=1/VWRSI_LEN, adjust=False).mean()
    avg_down = down_vol.ewm(alpha=1/VWRSI_LEN, adjust=False).mean()
    rs = avg_up / avg_down.replace(0, np.nan)
    df["vwrsi"] = 100 - (100 / (1 + rs))

    # 4. กรอบ Swing 16 แท่ง (4 ชม.)
    df["swing_high"] = df["high"].rolling(16).max().shift(1)
    df["swing_low"] = df["low"].rolling(16).min().shift(1)

    # 5. ATR (14) และ Z-Score สำหรับ Dashboard
    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift(1)).abs(), (df["low"] - df["close"].shift(1)).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(ATR_LEN).mean()

    m100 = df["close"].rolling(100).mean()
    s100 = df["close"].rolling(100).std()
    df["macro_z"] = (df["close"] - m100) / s100.replace(0, np.nan)
    m14 = df["close"].rolling(14).mean()
    s14 = df["close"].rolling(14).std()
    df["fast_z"] = (df["close"] - m14) / s14.replace(0, np.nan)

    return df
