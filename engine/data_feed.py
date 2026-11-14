import os
import requests
import pandas as pd
import yfinance as yf
from engine.config import HISTORY_CSV

def to_unix_seconds(series):
    return (pd.to_datetime(series, utc=True).astype("int64") // 10**9).astype(int)

def fetch_market_data():
    os.makedirs(os.path.dirname(HISTORY_CSV), exist_ok=True)
    api_key = os.getenv("TWELVE_DATA_KEY", "").strip()
    new_df = pd.DataFrame()
    source_name = "Yahoo Finance (Free Feed)"

    if api_key:
        try:
            url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=5000&apikey={api_key}"
            res = requests.get(url, timeout=30).json()
            if "values" in res:
                new_df = pd.DataFrame(res["values"])
                new_df["datetime"] = pd.to_datetime(new_df["datetime"], utc=True)
                for col in ["open", "high", "low", "close"]:
                    new_df[col] = pd.to_numeric(new_df[col], errors="coerce")
                new_df = new_df[["datetime", "open", "high", "low", "close"]].dropna()
                source_name = "TwelveData Spot XAU/USD (Modular V5)"
            else:
                print(f"Warning Twelve Data API: {res.get('message', res)}")
        except Exception as e:
            print(f"Warning Twelve Data Request Failed: {e}")

    # Fallback: หาก API ขัดข้องให้โหลดจากไฟล์ประวัติเดิมที่เคยบันทึกไว้ก่อน
    if new_df.empty and os.path.exists(HISTORY_CSV):
        old_df = pd.read_csv(HISTORY_CSV)
        old_df["datetime"] = pd.to_datetime(old_df["datetime"], utc=True)
        for col in ["open", "high", "low", "close"]:
            old_df[col] = pd.to_numeric(old_df[col], errors="coerce")
        new_df = old_df[["datetime", "open", "high", "low", "close"]].dropna()
        source_name = str(old_df["source"].iloc[-1]) if "source" in old_df.columns else "Cached Spot XAU/USD"

    # Fallback สุดท้ายหากยังไม่มีไฟล์เดิมเลย ใช้ Yahoo Finance
    if new_df.empty:
        ticker = yf.Ticker("GC=F")
        df_y = ticker.history(period="60d", interval="15m").reset_index()
        time_col = "Datetime" if "Datetime" in df_y.columns else "Date"
        df_y["datetime"] = pd.to_datetime(df_y[time_col], utc=True)
        new_df = df_y.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})[["datetime", "open", "high", "low", "close"]].dropna()
        source_name = "Yahoo Finance GC=F (Fallback)"

    new_df["ts"] = to_unix_seconds(new_df["datetime"])

    if os.path.exists(HISTORY_CSV):
        try:
            old_df = pd.read_csv(HISTORY_CSV)
            if "source" in old_df.columns and "TwelveData" in str(old_df["source"].iloc[-1]) and "TwelveData" in source_name:
                old_df["datetime"] = pd.to_datetime(old_df["datetime"], utc=True)
                old_df["ts"] = to_unix_seconds(old_df["datetime"])
                combined = pd.concat([old_df[["datetime", "ts", "open", "high", "low", "close"]], new_df], ignore_index=True)
            else:
                combined = new_df
        except Exception:
            combined = new_df
    else:
        combined = new_df

    combined = combined.drop_duplicates(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    combined = combined[combined["datetime"].dt.dayofweek < 5].reset_index(drop=True)
    combined["source"] = source_name
    combined.to_csv(HISTORY_CSV, index=False)
    return combined, source_name
