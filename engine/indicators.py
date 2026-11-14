import numpy as np
import pandas as pd
from engine.config import ATR_LEN, VWRSI_LEN, H1_EMA_LEN

def compute_all_features(df):
    d = df.copy()
    d["thai_dt"] = d["datetime"] + pd.Timedelta(hours=7)
    d["thai_date"] = d["thai_dt"].dt.date
    d["thai_hour"] = d["thai_dt"].dt.hour
    d["thai_minute"] = d["thai_dt"].dt.minute
    d["thai_mins"] = d["thai_hour"] * 60 + d["thai_minute"]

    # 1. Dynamic Volatility (ATR & Self-Normalizing ATR Percentile)
    prev_c = d["close"].shift(1)
    tr = pd.concat([
        (d["high"] - d["low"]).abs(),
        (d["high"] - prev_c).abs(),
        (d["low"] - prev_c).abs()
    ], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / ATR_LEN, adjust=False).mean()
    d["atr_base"] = d["atr"].rolling(100, min_periods=20).mean()
    d["atr_ratio"] = (d["atr"] / d["atr_base"]).fillna(1.0)

    # 2. Kaufman Efficiency Ratio (ER) + Dynamic Percentile Rank (ปรับตามสภาพตลาด 100 แท่งล่าสุด)
    net_change = (d["close"] - d["close"].shift(14)).abs()
    sum_volatility = (d["close"] - d["close"].shift(1)).abs().rolling(14).sum()
    d["er"] = (net_change / (sum_volatility + 1e-12)).fillna(0.25)
    d["er_med"] = d["er"].rolling(100, min_periods=20).median().fillna(0.25)
    d["er_q65"] = d["er"].rolling(100, min_periods=20).quantile(0.65).fillna(0.32)

    # 3. Kaufman Adaptive Moving Average (KAMA): ปรับความไวตามค่า ER ของตลาดอัตโนมัติ
    close_arr = d["close"].values
    er_arr = d["er"].values
    kama = np.zeros(len(d))
    kama[0] = close_arr[0]
    fast_sc = 2.0 / (4.0 + 1.0)
    slow_sc = 2.0 / (30.0 + 1.0)
    for idx in range(1, len(d)):
        sc = (er_arr[idx] * (fast_sc - slow_sc) + slow_sc) ** 2
        kama[idx] = kama[idx - 1] + sc * (close_arr[idx] - kama[idx - 1])
    d["kama"] = kama

    # 4. Exact Session VWAP (รีเซ็ตทุก 08:00 น. เวลาไทย)
    tp = (d["high"] + d["low"] + d["close"]) / 3.0
    pseudo_vol = (tr / d["atr"]).fillna(1.0).clip(0.3, 4.0)
    d["session_id"] = (d["thai_dt"] - pd.Timedelta(hours=8)).dt.date
    d["pv"] = tp * pseudo_vol
    d["pvol"] = pseudo_vol
    d["cum_pv"] = d.groupby("session_id")["pv"].cumsum()
    d["cum_vol"] = d.groupby("session_id")["pvol"].cumsum()
    d["vwap"] = d["cum_pv"] / d["cum_vol"]

    # 5. Volume-Weighted RSI (14) + Dynamic RSI Bands (ปรับเพดานตามโมเมนตัมช่วงนั้น)
    delta = d["close"].diff()
    up = np.where(delta > 0, delta * pseudo_vol, 0.0)
    down = np.where(delta < 0, (-delta) * pseudo_vol, 0.0)
    roll_up = pd.Series(up, index=d.index).ewm(alpha=1 / VWRSI_LEN, adjust=False).mean()
    roll_down = pd.Series(down, index=d.index).ewm(alpha=1 / VWRSI_LEN, adjust=False).mean()
    rs = roll_up / (roll_down + 1e-12)
    d["vwrsi"] = 100.0 - (100.0 / (1.0 + rs))
    d["rsi_mean"] = d["vwrsi"].rolling(100, min_periods=20).mean().fillna(50.0)
    d["rsi_std"] = d["vwrsi"].rolling(100, min_periods=20).std().fillna(10.0)

    # 6. Adaptive Z-Score (เทียบกับเส้น KAMA ที่ปรับตามสภาวะตลาด + Dynamic Quantile Thresholds)
    d["macro_mean"] = d["close"].rolling(96).mean()
    d["macro_std"] = d["close"].rolling(96).std()
    d["macro_z"] = (d["close"] - d["macro_mean"]) / (d["macro_std"] + 1e-12)

    d["fast_mean"] = d["close"].rolling(20).mean()
    d["fast_std"] = d["close"].rolling(20).std()
    d["fast_z"] = (d["close"] - d["fast_mean"]) / (d["fast_std"] + 1e-12)
    # กรอบยืดหยุ่นของ Z-Score คำนวณใหม่ทุกแท่งจากประวัติ 100 แท่งล่าสุด
    d["z_upper_dyn"] = d["fast_z"].rolling(100, min_periods=20).quantile(0.92).clip(1.45, 2.30).fillna(1.65)
    d["z_lower_dyn"] = d["fast_z"].rolling(100, min_periods=20).quantile(0.08).clip(-2.30, -1.45).fillna(-1.65)

    # 7. Multi-Timeframe H1 & H4 Trend Alignment
    d_idx = d.set_index("datetime")
    h1 = d_idx["close"].resample("1h").last().dropna()
    h1_ema = h1.ewm(span=H1_EMA_LEN, adjust=False).mean()
    h1_df = pd.DataFrame({"h1_close": h1, "h1_ema": h1_ema}).shift(1)

    h4 = d_idx["close"].resample("4h").last().dropna()
    h4_ema = h4.ewm(span=21, adjust=False).mean()
    h4_df = pd.DataFrame({"h4_close": h4, "h4_ema": h4_ema}).shift(1)

    merged = pd.merge_asof(d.sort_values("datetime"), h1_df.reset_index().sort_values("datetime"), on="datetime", direction="backward")
    merged = pd.merge_asof(merged.sort_values("datetime"), h4_df.reset_index().sort_values("datetime"), on="datetime", direction="backward")
    return merged.reset_index(drop=True)
