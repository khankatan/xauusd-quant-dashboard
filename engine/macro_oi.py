import pandas as pd
import numpy as np
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

def compute_volume_profile_poc(d, window=96, bins=40):
    """
    คำนวณตำแหน่ง Volume Profile Point of Control (POC) แบบ Rolling 
    เพื่อหาโซนราคาที่มีการสะสมวอลุ่มหนาแน่นที่สุด
    """
    close_vals = d['close'].values
    high_vals = d['high'].values
    low_vals = d['low'].values
    # ใช้ True Range * atr_ratio เป็น Proxy สำหรับ Volume ในแต่ละแท่ง M15
    vol_vals = (d['high'] - d['low']).abs() * d.get('atr_ratio', 1.0)
    
    n = len(d)
    poc_arr = np.zeros(n)
    dist_from_poc = np.zeros(n)
    
    for i in range(window, n):
        w_high = high_vals[i-window:i]
        w_low = low_vals[i-window:i]
        w_vol = vol_vals[i-window:i]
        
        min_p = w_low.min()
        max_p = w_high.max()
        if max_p - min_p < 1e-5:
            poc_arr[i] = close_vals[i]
            continue
            
        hist, bin_edges = np.histogram(w_high, bins=bins, range=(min_p, max_p), weights=w_vol)
        max_bin_idx = np.argmax(hist)
        poc = (bin_edges[max_bin_idx] + bin_edges[max_bin_idx+1]) / 2.0
        poc_arr[i] = poc
        dist_from_poc[i] = (close_vals[i] - poc) / (d['atr'].iloc[i] + 1e-9)
        
    d['vp_poc'] = poc_arr
    d['vp_dist_atr'] = dist_from_poc
    return d

def fetch_macro_oi_and_dxy(m15_df):
    df = m15_df.copy()
    df["macro_bull_conv"] = False
    df["macro_bear_conv"] = False
    df["macro_status"] = "OI+DXY+POC: STANDARD (0.35%)"

    # คำนวณ Volume Profile POC ประกอบเป็ฯด่านยืนยันวอลุ่ม
    df = compute_volume_profile_poc(df, window=96, bins=40)

    if not YFINANCE_AVAILABLE:
        return df

    try:
        gc = yf.Ticker("GC=F").history(period="2y", interval="1d")
        dxy = yf.Ticker("DX-Y.NYB").history(period="2y", interval="1d")

        if gc.empty:
            return df

        gc = gc.reset_index()
        date_col = "Date" if "Date" in gc.columns else "Datetime"
        gc["m_date"] = pd.to_datetime(gc[date_col]).dt.tz_localize(None).dt.date

        gc["gc_ret"] = gc["Close"].pct_change()
        gc["vol_ma10"] = gc["Volume"].rolling(10).mean()
        gc["vol_surge"] = gc["Volume"] > (gc["vol_ma10"] * 1.05)

        if "Open Interest" in gc.columns and gc["Open Interest"].notna().sum() > 5:
            gc["oi_diff"] = gc["Open Interest"].diff()
            gc["oi_rising"] = gc["oi_diff"] > 0
        else:
            gc["oi_rising"] = gc["vol_surge"]

        if not dxy.empty:
            dxy = dxy.reset_index()
            d_col = "Date" if "Date" in dxy.columns else "Datetime"
            dxy["m_date"] = pd.to_datetime(dxy[d_col]).dt.tz_localize(None).dt.date
            dxy["dxy_ema10"] = dxy["Close"].ewm(span=10, adjust=False).mean()
            dxy["dxy_bear"] = dxy["Close"] < dxy["dxy_ema10"]
            dxy["dxy_bull"] = dxy["Close"] > dxy["dxy_ema10"]
            gc = gc.merge(dxy[["m_date", "dxy_bear", "dxy_bull"]], on="m_date", how="left")
            gc["dxy_bear"] = gc["dxy_bear"].fillna(True)
            gc["dxy_bull"] = gc["dxy_bull"].fillna(True)
        else:
            gc["dxy_bear"] = True
            gc["dxy_bull"] = True

        gc["conv_long"] = (gc["gc_ret"] > 0) & (gc["oi_rising"] | gc["vol_surge"]) & gc["dxy_bear"]
        gc["conv_short"] = (gc["gc_ret"] < 0) & (gc["oi_rising"] | gc["vol_surge"]) & gc["dxy_bull"]

        gc["conv_long_today"] = gc["conv_long"].shift(1).fillna(False)
        gc["conv_short_today"] = gc["conv_short"].shift(1).fillna(False)

        lookup = gc.set_index("m_date")[["conv_long_today", "conv_short_today"]].to_dict("index")

        def map_conv(d):
            info = lookup.get(d, None)
            if not info:
                return False, False
            return bool(info["conv_long_today"]), bool(info["conv_short_today"])

        mapped = df["thai_date"].apply(map_conv)
        base_bull = [m[0] for m in mapped]
        base_bear = [m[1] for m in mapped]

        # เงื่อนไขใหม่: Macro Conviction จะสมบูรณ์ก็ต่อเมื่อราคายืนยันถูกฝั่งของ Volume Profile POC ด้วย
        # - ฝั่งซื้อ: ราคาต้องอยู่เหนือ POC หรือไม่ต่ำกว่า POC เกิน 1.5 ATR (กำลังสะสมพลังหรือเบรกขึ้น)
        # - ฝั่งขาย: ราคาต้องอยู่ใต้ POC หรือไม่สูงกว่า POC เกิน 1.5 ATR (กำลังสะสมแรงกดหรือเบรกหลุด)
        vp_bull_ok = (df["close"] >= df["vp_poc"]) | (df["vp_dist_atr"] >= -1.5)
        vp_bear_ok = (df["close"] <= df["vp_poc"]) | (df["vp_dist_atr"] <= 1.5)

        df["macro_bull_conv"] = [b and o for b, o in zip(base_bull, vp_bull_ok)]
        df["macro_bear_conv"] = [b and o for b, o in zip(base_bear, vp_bear_ok)]

        last_l = df["macro_bull_conv"].iloc[-1]
        last_s = df["macro_bear_conv"].iloc[-1]
        if last_l:
            df["macro_status"] = "OI+DXY+POC: BUY CONVICTION (0.50%)"
        elif last_s:
            df["macro_status"] = "OI+DXY+POC: SELL CONVICTION (0.50%)"
        else:
            df["macro_status"] = "OI+DXY+POC: STANDARD (0.35%)"

    except Exception as e:
        print(f"Macro OI/DXY + VP POC Fetch Warning: {e}")

    return df
