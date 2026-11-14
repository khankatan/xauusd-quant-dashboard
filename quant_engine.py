import os
import json
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

# ==========================================
# 1. ตั้งค่าพารามิเตอร์กลยุทธ์ (ตรงกับที่จูนไว้)
# ==========================================
INITIAL_CAPITAL = 100000.0
RISK_PER_TRADE_PCT = 0.25
DAILY_TARGET_PCT = 0.30
MACRO_Z_LEN = 100
FAST_Z_LEN = 14
ATR_LEN = 14
SL_ATR_MULT = 2.0
TP_ATR_MULT = 4.5

os.makedirs("data", exist_ok=True)

# ==========================================
# 2. ดึงข้อมูลกราฟกลาง XAUUSD M15 (ฟรี 100%)
# ==========================================
def fetch_xauusd_m15():
    api_key = os.getenv("TWELVE_DATA_KEY", "").strip()
    # ทางเลือก A: ใช้ Twelve Data (ถ้าใส่ Key ฟรีใน GitHub Secrets)
    if api_key:
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=250&apikey={api_key}"
        res = requests.get(url, timeout=15).json()
        if "values" in res:
            df = pd.DataFrame(res["values"])
            df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
            for col in ["open", "high", "low", "close"]:
                df[col] = df[col].astype(float)
            df = df.sort_values("datetime").reset_index(drop=True)
            return df, "TwelveData (Spot XAU/USD)"

    # ทางเลือก B: ใช้ Yahoo Finance GC=F / XAUUSD=X (ฟรี ไม่ต้องใช้ API Key)
    ticker = yf.Ticker("GC=F")
    df = ticker.history(period="5d", interval="15m")
    if df.empty:
        ticker = yf.Ticker("XAUUSD=X")
        df = ticker.history(period="5d", interval="15m")
    df = df.reset_index()
    time_col = "Datetime" if "Datetime" in df.columns else "Date"
    df["datetime"] = pd.to_datetime(df[time_col], utc=True)
    df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})
    df = df[["datetime", "open", "high", "low", "close"]].dropna().tail(250).reset_index(drop=True)
    return df, "Yahoo Finance (Free Feed)"

# ==========================================
# 3. คำนวณสมการ Quant (Z-Score & ATR)
# ==========================================
def compute_signals(df):
    # Macro Z-Score (100) & Fast Z-Score (14)
    df["macro_mean"] = df["close"].rolling(MACRO_Z_LEN).mean()
    df["macro_std"] = df["close"].rolling(MACRO_Z_LEN).std()
    df["macro_z"] = (df["close"] - df["macro_mean"]) / df["macro_std"]

    df["fast_mean"] = df["close"].rolling(FAST_Z_LEN).mean()
    df["fast_std"] = df["close"].rolling(FAST_Z_LEN).std()
    df["fast_z"] = (df["close"] - df["fast_mean"]) / df["fast_std"]

    # ATR (14)
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift(1))
    low_close = np.abs(df["low"] - df["close"].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(ATR_LEN).mean()

    # ใช้แท่งที่ปิดสมบูรณ์ล่าสุด (index -2) เพื่อป้องกัน Look-ahead Bias
    curr = df.iloc[-2]
    prev = df.iloc[-3]
    macro_prev2 = df.iloc[-4]["macro_z"]

    is_bull_regime = (curr["macro_z"] > 0.0) and (curr["macro_z"] > macro_prev2)
    is_bear_regime = (curr["macro_z"] < -0.3) and (curr["macro_z"] < macro_prev2)

    # เช็กช่วงเวลา London + NY Session (06:00 - 18:00 UTC = 13:00 - 01:00 น. ไทย)
    bar_hour = curr["datetime"].hour
    in_session = 6 <= bar_hour <= 18

    long_signal = in_session and is_bull_regime and (prev["fast_z"] < -0.4) and (curr["fast_z"] > prev["fast_z"]) and (curr["close"] > prev["high"])
    short_signal = in_session and is_bear_regime and (prev["fast_z"] > 0.4) and (curr["fast_z"] < prev["fast_z"]) and (curr["close"] < prev["low"])

    signal_type = "WAIT"
    entry_price = float(curr["close"])
    sl_price = None
    tp_price = None
    be_trigger = None
    lot_size = 0.0

    atr_val = float(curr["atr"])
    sl_dist = atr_val * SL_ATR_MULT
    tp_dist = atr_val * TP_ATR_MULT

    # คำนวณ Lot Size (1 Standard Lot XAUUSD = 100 oz -> $100 ต่อการขยับ $1)
    risk_money = INITIAL_CAPITAL * (RISK_PER_TRADE_PCT / 100.0) # $250
    if sl_dist > 0:
        lot_size = round(risk_money / (sl_dist * 100.0), 2)

    if long_signal:
        signal_type = "LONG"
        sl_price = round(entry_price - sl_dist, 2)
        tp_price = round(entry_price + tp_dist, 2)
        be_trigger = round(entry_price + (sl_dist * 1.5), 2)
    elif short_signal:
        signal_type = "SHORT"
        sl_price = round(entry_price + sl_dist, 2)
        tp_price = round(entry_price - tp_dist, 2)
        be_trigger = round(entry_price - (sl_dist * 1.5), 2)

    # เตรียมแท่งเทียน 120 แท่งล่าสุดส่งให้หน้าเว็บวาดกราฟ
    candles = []
    for _, row in df.tail(120).iterrows():
        candles.append({
            "time": int(row["datetime"].timestamp()),
            "open": round(float(row["open"]), 2),
            "high": round(float(row["high"]), 2),
            "low": round(float(row["low"]), 2),
            "close": round(float(row["close"]), 2)
        })

    state = {
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "data_source": source_name,
        "current_price": round(float(df.iloc[-1]["close"]), 2),
        "macro_z": round(float(curr["macro_z"]), 3),
        "fast_z": round(float(curr["fast_z"]), 3),
        "atr": round(atr_val, 2),
        "regime": "BULLISH" if is_bull_regime else ("BEARISH" if is_bear_regime else "NEUTRAL"),
        "in_session": in_session,
        "signal": {
            "type": signal_type,
            "entry": round(entry_price, 2) if signal_type != "WAIT" else None,
            "sl": sl_price,
            "tp": tp_price,
            "be_trigger": be_trigger,
            "lot_size_100k": lot_size,
            "risk_usd": risk_money
        },
        "risk_rules": {
            "risk_per_trade": "0.25% ($250)",
            "rolling_2hr_cap": "1.00% ($1,000)",
            "daily_target": "+0.30% ($300) Lock",
            "daily_dd_limit": "5.00% ($5,000)"
        },
        "candles": candles
    }
    return state

if __name__ == "__main__":
    df, source_name = fetch_xauusd_m15()
    state = compute_signals(df)
    with open("data/state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    print("Updated state.json successfully:", state["signal"]["type"])
