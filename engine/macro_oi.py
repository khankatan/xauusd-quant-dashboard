import pandas as pd
import numpy as np
import yfinance as yf

def fetch_macro_oi_and_dxy(m15_df):
    df = m15_df.copy()
    df["macro_bull_conv"] = False
    df["macro_bear_conv"] = False
    df["macro_status"] = "OI+DXY: STANDARD (0.35%)"

    try:
        gc = yf.Ticker("GC=F").history(period="90d", interval="1d")
        dxy = yf.Ticker("DX-Y.NYB").history(period="90d", interval="1d")

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
        df["macro_bull_conv"] = [m[0] for m in mapped]
        df["macro_bear_conv"] = [m[1] for m in mapped]

        last_l = df["macro_bull_conv"].iloc[-1]
        last_s = df["macro_bear_conv"].iloc[-1]
        if last_l:
            df["macro_status"] = "OI+DXY: BUY CONVICTION (0.50%)"
        elif last_s:
            df["macro_status"] = "OI+DXY: SELL CONVICTION (0.50%)"
        else:
            df["macro_status"] = "OI+DXY: STANDARD (0.35%)"

    except Exception as e:
        print(f"Macro OI/DXY Fetch Warning (Fallback to 0.35%): {e}")

    return df
