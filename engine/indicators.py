import numpy as np
import pandas as pd
from engine.config import ATR_LEN, VWRSI_LEN, H1_EMA_LEN

def compute_hilbert_dominant_cycle(price_arr, min_p=10, max_p=28):
    n = len(price_arr)
    smooth = np.zeros(n)
    detrender = np.zeros(n)
    I1 = np.zeros(n)
    Q1 = np.zeros(n)
    jI = np.zeros(n)
    jQ = np.zeros(n)
    I2 = np.zeros(n)
    Q2 = np.zeros(n)
    Re = np.zeros(n)
    Im = np.zeros(n)
    period = np.full(n, 14.0)
    smooth_period = np.full(n, 14.0)

    for i in range(6, n):
        smooth[i] = (4.0 * price_arr[i] + 3.0 * price_arr[i - 1] + 2.0 * price_arr[i - 2] + price_arr[i - 3]) / 10.0
        adj = 0.075 * period[i - 1] + 0.54
        detrender[i] = (0.0962 * smooth[i] + 0.5769 * smooth[i - 2] - 0.5769 * smooth[i - 4] - 0.0962 * smooth[i - 6]) * adj
        Q1[i] = (0.0962 * detrender[i] + 0.5769 * detrender[i - 2] - 0.5769 * detrender[i - 4] - 0.0962 * detrender[i - 6]) * adj
        I1[i] = detrender[i - 3]
        jI[i] = (0.0962 * I1[i] + 0.5769 * I1[i - 2] - 0.5769 * I1[i - 4] - 0.0962 * I1[i - 6]) * adj
        jQ[i] = (0.0962 * Q1[i] + 0.5769 * Q1[i - 2] - 0.5769 * Q1[i - 4] - 0.0962 * Q1[i - 6]) * adj
        I2[i] = 0.2 * (I1[i] - jQ[i]) + 0.8 * I2[i - 1]
        Q2[i] = 0.2 * (Q1[i] + jI[i]) + 0.8 * Q2[i - 1]
        Re[i] = 0.2 * (I2[i] * I2[i - 1] + Q2[i] * Q2[i - 1]) + 0.8 * Re[i - 1]
        Im[i] = 0.2 * (I2[i] * Q2[i - 1] - Q2[i] * I2[i - 1]) + 0.8 * Im[i - 1]

        raw_p = period[i - 1]
        if abs(Im[i]) > 1e-9 and abs(Re[i]) > 1e-9:
            angle = np.arctan2(Im[i], Re[i])
            if abs(angle) > 0.01:
                raw_p = (2.0 * np.pi) / abs(angle)
        raw_p = np.clip(raw_p, 0.67 * period[i - 1], 1.5 * period[i - 1])
        raw_p = np.clip(raw_p, float(min_p), float(max_p))
        period[i] = 0.2 * raw_p + 0.8 * period[i - 1]
        smooth_period[i] = 0.33 * period[i] + 0.67 * smooth_period[i - 1]

    return np.rint(smooth_period).astype(int)

def compute_all_features(df):
    d = df.copy()
    d["thai_dt"] = d["datetime"] + pd.Timedelta(hours=7)
    # แก้บั๊ก Midnight Lockout: ใช้วันทำการของเซสชัน (ตัดวันใหม่ตอน 04:00 น. หลังปิด Rollover 03:00 น.)
    # เพื่อไม่ให้ออเดอร์ที่ปิดระหว่าง 00:00 - 03:00 น. ไปล็อกโควตาของวันรุ่งขึ้น!
    d["thai_date"] = (d["thai_dt"] - pd.Timedelta(hours=4)).dt.date
    d["thai_hour"] = d["thai_dt"].dt.hour
    d["thai_minute"] = d["thai_dt"].dt.minute
    d["thai_mins"] = d["thai_hour"] * 60 + d["thai_minute"]

    # 1. True Range, ATR & Relative Volatility Ratio
    prev_c = d["close"].shift(1)
    tr = pd.concat([
        (d["high"] - d["low"]).abs(),
        (d["high"] - prev_c).abs(),
        (d["low"] - prev_c).abs()
    ], axis=1).max(axis=1)
    d["atr"] = tr.ewm(alpha=1 / ATR_LEN, adjust=False).mean()
    d["atr_base"] = d["atr"].rolling(100, min_periods=20).mean()
    d["atr_ratio"] = (d["atr"] / d["atr_base"]).fillna(1.0)

    # 2. Hilbert Dominant Cycle (P_t), Adaptive CHOP, Structure Box & Dynamic Tenkan/Kijun
    hl2 = ((d["high"] + d["low"]) / 2.0).values
    dom_cycle = compute_hilbert_dominant_cycle(hl2, min_p=10, max_p=28)
    d["dom_cycle"] = dom_cycle

    high_arr = d["high"].values
    low_arr = d["low"].values
    close_arr = d["close"].values
    tr_arr = tr.values
    n = len(d)

    chop_arr = np.full(n, 50.0)
    er_arr = np.full(n, 0.30)
    struct_high_arr = np.zeros(n)
    struct_low_arr = np.zeros(n)
    tenkan_arr = np.zeros(n)
    kijun_arr = np.zeros(n)

    for i in range(n):
        p = int(dom_cycle[i])
        t_len = max(5, int(round(0.5 * p)))
        k_len = max(13, int(round(1.5 * p)))

        if i <= k_len:
            struct_high_arr[i] = high_arr[i]
            struct_low_arr[i] = low_arr[i]
            tenkan_arr[i] = close_arr[i]
            kijun_arr[i] = close_arr[i]
            continue

        sum_tr = np.sum(tr_arr[i - p + 1 : i + 1])
        hl_range = max(np.max(high_arr[i - p + 1 : i + 1]) - np.min(low_arr[i - p + 1 : i + 1]), 1e-9)
        chop_arr[i] = np.clip(100.0 * np.log10(max(sum_tr / hl_range, 1.0)) / np.log10(float(p)), 0.0, 100.0)

        net_chg = abs(close_arr[i] - close_arr[i - p])
        sum_abs = np.sum(np.abs(np.diff(close_arr[i - p : i + 1])))
        er_arr[i] = net_chg / (sum_abs + 1e-9)

        struct_high_arr[i] = np.max(high_arr[i - p : i])
        struct_low_arr[i] = np.min(low_arr[i - p : i])

        tenkan_arr[i] = 0.5 * (np.max(high_arr[i - t_len + 1 : i + 1]) + np.min(low_arr[i - t_len + 1 : i + 1]))
        kijun_arr[i] = 0.5 * (np.max(high_arr[i - k_len + 1 : i + 1]) + np.min(low_arr[i - k_len + 1 : i + 1]))

    d["chop"] = chop_arr
    d["er"] = er_arr
    d["struct_high"] = struct_high_arr
    d["struct_low"] = struct_low_arr
    d["tenkan"] = tenkan_arr
    d["kijun"] = kijun_arr

    # 3. KAMA & แคลคูลัสอนุพันธ์ (Slope & Acceleration)
    kama = np.zeros(n)
    kama[0] = close_arr[0]
    fast_sc = 2.0 / (3.0 + 1.0)
    slow_sc = 2.0 / (30.0 + 1.0)
    for i in range(1, n):
        sc = (er_arr[i] * (fast_sc - slow_sc) + slow_sc) ** 2
        kama[i] = kama[i - 1] + sc * (close_arr[i] - kama[i - 1])
    d["kama"] = kama
    d["kama_slope"] = (d["kama"] - d["kama"].shift(1)) / (d["atr"] + 1e-9)
    d["price_vel"] = (d["close"] - d["close"].shift(1)) / (d["atr"] + 1e-9)
    d["price_accel"] = d["price_vel"] - d["price_vel"].shift(1)

    # 4. Exact Session VWAP & VWRSI
    tp = (d["high"] + d["low"] + d["close"]) / 3.0
    pseudo_vol = (tr / d["atr"]).fillna(1.0).clip(0.3, 4.0)
    d["session_id"] = (d["thai_dt"] - pd.Timedelta(hours=8)).dt.date
    d["pv"] = tp * pseudo_vol
    d["pvol"] = pseudo_vol
    d["cum_pv"] = d.groupby("session_id")["pv"].cumsum()
    d["cum_vol"] = d.groupby("session_id")["pvol"].cumsum()
    d["vwap"] = d["cum_pv"] / d["cum_vol"]

    delta = d["close"].diff()
    up = np.where(delta > 0, delta * pseudo_vol, 0.0)
    down = np.where(delta < 0, (-delta) * pseudo_vol, 0.0)
    roll_up = pd.Series(up, index=d.index).ewm(alpha=1 / VWRSI_LEN, adjust=False).mean()
    roll_down = pd.Series(down, index=d.index).ewm(alpha=1 / VWRSI_LEN, adjust=False).mean()
    rs = roll_up / (roll_down + 1e-12)
    d["vwrsi"] = 100.0 - (100.0 / (1.0 + rs))

    # 5. Macro & Fast Z-Score
    d["macro_mean"] = d["close"].rolling(96).mean()
    d["macro_std"] = d["close"].rolling(96).std()
    d["macro_z"] = (d["close"] - d["macro_mean"]) / (d["macro_std"] + 1e-12)

    d["fast_mean"] = d["close"].rolling(20).mean()
    d["fast_std"] = d["close"].rolling(20).std()
    d["fast_z"] = (d["close"] - d["fast_mean"]) / (d["fast_std"] + 1e-12)

    # 6. Multi-Timeframe H1 & H4 Trend Alignment
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
