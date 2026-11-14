import os
import json
import math
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

INITIAL_CAPITAL = 100000.0
RISK_PER_TRADE_PCT = 0.60     # เสี่ยง 0.60% ต่อไม้ (ตามเทรนด์ H4 100% -> ชนะ 1 ไม้ได้ +0.95%)
DAILY_TARGET_PCT = 0.45       # กำไรถึง +0.45% ของวัน -> ล็อกกำไรหยุดทันที รอวันถัดไป
MAX_TRADES_PER_DAY = 2        # จำกัดไม่เกิน 2 ไม้/วัน
COMMISSION_PER_OZ = 0.035

H4_EMA_LEN = 34               # ตัวกรองทิศทางหลักระดับ H4 (Strict Trend Alignment)
SWING_LOOKBACK = 12           # กรอบ Liquidity Sweep 3 ชม. (12 แท่ง M15)
VWRSI_LEN = 14
ATR_LEN = 14
SL_ATR_MULT = 2.2
TP_ATR_MULT = 3.5             # R:R 1:1.59
BE_TRIGGER_R = 1.2

os.makedirs("data", exist_ok=True)
HISTORY_CSV = "data/xauusd_m15_history.csv"
TRADES_CSV = "data/all_trades.csv"

def to_unix_seconds(series):
    return series.apply(lambda x: int(x.timestamp()))

def fetch_and_store_history():
    api_key = os.getenv("TWELVE_DATA_KEY", "").strip()
    new_df = pd.DataFrame()
    source_name = "Yahoo Finance (Free Feed)"

    if api_key:
        url = f"https://api.twelvedata.com/time_series?symbol=XAU/USD&interval=15min&outputsize=5000&apikey={api_key}"
        res = requests.get(url, timeout=30).json()
        if "values" in res:
            new_df = pd.DataFrame(res["values"])
            new_df["datetime"] = pd.to_datetime(new_df["datetime"], utc=True)
            for col in ["open", "high", "low", "close"]:
                new_df[col] = pd.to_numeric(new_df[col], errors="coerce")
            new_df = new_df[["datetime", "open", "high", "low", "close"]].dropna()
            source_name = "TwelveData Spot XAU/USD (V8.1 Strict H4-Trend + VWAP)"
        else:
            raise RuntimeError(f"Twelve Data Error: {res.get('message', res)}")
    else:
        ticker = yf.Ticker("GC=F")
        df_y = ticker.history(period="60d", interval="15m").reset_index()
        time_col = "Datetime" if "Datetime" in df_y.columns else "Date"
        df_y["datetime"] = pd.to_datetime(df_y[time_col], utc=True)
        new_df = df_y.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close"})[["datetime", "open", "high", "low", "close"]].dropna()

    new_df["ts"] = to_unix_seconds(new_df["datetime"])

    if os.path.exists(HISTORY_CSV):
        try:
            old_df = pd.read_csv(HISTORY_CSV)
            if "source" in old_df.columns and "TwelveData" in str(old_df["source"].iloc[-1]) and "TwelveData" in source_name:
                old_df["datetime"] = pd.to_datetime(old_df["datetime"], utc=True)
                old_df["ts"] = to_unix_seconds(old_df["datetime"])
                combined = pd.concat([old_df[["datetime", "ts", "open", "high", "low", "close"]], new_df])
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

def is_open_thai_market(utc_dt):
    # เปิดเทรดเต็มวัน 08:00 - 23:29 น. เวลาไทย (ไม่ตัดชั่วโมงระหว่างวันแบบ Curve-Fitting)
    # หยุดเปิดไม้ใหม่หลัง 23:30 น. เพื่อป้องกันออเดอร์ค้างไปโดน Rollover ตอนตี 2 ครึ่ง
    thai_dt = utc_dt + pd.Timedelta(hours=7)
    mins_of_day = thai_dt.hour * 60 + thai_dt.minute
    return (8 * 60) <= mins_of_day <= (23 * 60 + 30)

def build_institutional_features(df):
    df = df.copy()
    # 1. สร้างแท่งเทียน H4 จาก M15 (Zero Look-Ahead ด้วย shift(1))
    df_h4 = df.set_index("datetime").resample("4h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()
    df_h4["h4_ema"] = df_h4["close"].ewm(span=H4_EMA_LEN, adjust=False).mean()
    df_h4_shifted = df_h4[["close", "h4_ema"]].shift(1).rename(columns={"close": "h4_close"})

    df["h4_bucket"] = df["datetime"].dt.floor("4h")
    df = df.merge(df_h4_shifted, left_on="h4_bucket", right_index=True, how="left")
    df[["h4_close", "h4_ema"]] = df[["h4_close", "h4_ema"]].ffill()

    # 2. Synthetic Tick Volume & Session VWAP
    df["tick_vol"] = (df["high"] - df["low"]).replace(0, 0.01)
    df["typical_price"] = (df["high"] + df["low"] + df["close"]) / 3.0

    df["session_date"] = df["datetime"].dt.date
    df["pv"] = df["typical_price"] * df["tick_vol"]
    df["cum_pv"] = df.groupby("session_date")["pv"].cumsum()
    df["cum_vol"] = df.groupby("session_date")["tick_vol"].cumsum()
    df["vwap"] = df["cum_pv"] / df["cum_vol"]

    df["vwap_diff_sq"] = ((df["typical_price"] - df["vwap"]) ** 2) * df["tick_vol"]
    df["vwap_std"] = np.sqrt(df.groupby("session_date")["vwap_diff_sq"].cumsum() / df["cum_vol"])
    df["vwap_upper"] = df["vwap"] + (1.15 * df["vwap_std"])
    df["vwap_lower"] = df["vwap"] - (1.15 * df["vwap_std"])

    # 3. Volume-Weighted RSI (VWRSI 14)
    delta = df["close"].diff()
    up_vol = delta.clip(lower=0) * df["tick_vol"]
    down_vol = (-delta.clip(upper=0)) * df["tick_vol"]
    avg_up = up_vol.ewm(alpha=1/VWRSI_LEN, adjust=False).mean()
    avg_down = down_vol.ewm(alpha=1/VWRSI_LEN, adjust=False).mean()
    rs = avg_up / avg_down.replace(0, np.nan)
    df["vwrsi"] = 100 - (100 / (1 + rs))

    # 4. กรอบสภาพคล่อง (Swing High / Low 12 แท่ง = 3 ชม.)
    df["swing_high"] = df["high"].rolling(SWING_LOOKBACK).max().shift(1)
    df["swing_low"] = df["low"].rolling(SWING_LOOKBACK).min().shift(1)

    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift(1)).abs(), (df["low"] - df["close"].shift(1)).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(ATR_LEN).mean()

    m100 = df["close"].rolling(100).mean()
    s100 = df["close"].rolling(100).std()
    df["macro_z"] = (df["close"] - m100) / s100.replace(0, np.nan)
    m14 = df["close"].rolling(14).mean()
    s14 = df["close"].rolling(14).std()
    df["fast_z"] = (df["close"] - m14) / s14.replace(0, np.nan)

    return df

def run_quant_backtest(df, source_name):
    df = build_institutional_features(df)

    equity = INITIAL_CAPITAL
    peak_equity = INITIAL_CAPITAL
    max_dd_pct = 0.0

    current_day = None
    daily_start_eq = INITIAL_CAPITAL
    days_hit_target = 0
    today_target_logged = False
    trades_today = 0

    pos = None
    closed_trades = []
    equity_curve = []

    start_idx = 110
    for i in range(start_idx, len(df) - 1):
        bar = df.iloc[i]
        prev = df.iloc[i - 1]
        if pd.isna(bar["vwap"]) or pd.isna(bar["vwrsi"]) or pd.isna(bar["atr"]) or pd.isna(bar["swing_high"]) or pd.isna(bar["h4_ema"]):
            continue

        dt = bar["datetime"]
        thai_dt = dt + pd.Timedelta(hours=7)
        bar_date = thai_dt.date()
        now_ts = int(bar["ts"])

        if current_day != bar_date:
            current_day = bar_date
            daily_start_eq = equity
            today_target_logged = False
            trades_today = 0

        if pos is not None:
            exit_price = None
            exit_reason = None

            if pos["type"] == "LONG":
                if not pos["is_be"] and bar["high"] >= pos["be_trigger"]:
                    pos["sl"] = pos["entry"] + (pos["atr"] * 0.1)
                    pos["is_be"] = True
                if bar["low"] <= pos["sl"]:
                    exit_price = pos["sl"]
                    exit_reason = "V8.1-BE+" if pos["is_be"] else "V8.1-SL"
                elif bar["high"] >= pos["tp"]:
                    exit_price = pos["tp"]
                    exit_reason = "V8.1-TP"
                elif thai_dt.hour == 2 and thai_dt.minute >= 30:
                    exit_price = float(bar["close"])
                    exit_reason = "Rollover"

                if exit_price is not None:
                    net_pnl = ((exit_price - pos["entry"]) * pos["oz"]) - pos["comm"]
                    equity += net_pnl
                    closed_trades.append({
                        "entry_str": pos["entry_str"], "exit_str": dt.strftime("%Y-%m-%d %H:%M"),
                        "entry_time": pos["entry_time"], "exit_time": now_ts,
                        "entry_hour_utc": pos["entry_hour"], "type": "LONG",
                        "entry": round(pos["entry"], 2), "exit": round(exit_price, 2),
                        "pnl": round(net_pnl, 2), "reason": exit_reason
                    })
                    pos = None

            elif pos["type"] == "SHORT":
                if not pos["is_be"] and bar["low"] <= pos["be_trigger"]:
                    pos["sl"] = pos["entry"] - (pos["atr"] * 0.1)
                    pos["is_be"] = True
                if bar["high"] >= pos["sl"]:
                    exit_price = pos["sl"]
                    exit_reason = "V8.1-BE+" if pos["is_be"] else "V8.1-SL"
                elif bar["low"] <= pos["tp"]:
                    exit_price = pos["tp"]
                    exit_reason = "V8.1-TP"
                elif thai_dt.hour == 2 and thai_dt.minute >= 30:
                    exit_price = float(bar["close"])
                    exit_reason = "Rollover"

                if exit_price is not None:
                    net_pnl = ((pos["entry"] - exit_price) * pos["oz"]) - pos["comm"]
                    equity += net_pnl
                    closed_trades.append({
                        "entry_str": pos["entry_str"], "exit_str": dt.strftime("%Y-%m-%d %H:%M"),
                        "entry_time": pos["entry_time"], "exit_time": now_ts,
                        "entry_hour_utc": pos["entry_hour"], "type": "SHORT",
                        "entry": round(pos["entry"], 2), "exit": round(exit_price, 2),
                        "pnl": round(net_pnl, 2), "reason": exit_reason
                    })
                    pos = None

        peak_equity = max(peak_equity, equity)
        max_dd_pct = max(max_dd_pct, ((peak_equity - equity) / peak_equity) * 100.0)

        daily_pnl_pct = ((equity - daily_start_eq) / daily_start_eq) * 100.0
        if daily_pnl_pct >= DAILY_TARGET_PCT and not today_target_logged:
            days_hit_target += 1
            today_target_logged = True

        if pos is None and (not today_target_logged) and (trades_today < MAX_TRADES_PER_DAY):
            if is_open_thai_market(dt):
                # Strict H4 Trend Alignment: ห้ามเปิดออเดอร์สวนเทรนด์ใหญ่ระดับ H4 เด็ดขาด!
                h4_bull = bar["h4_close"] >= bar["h4_ema"]
                h4_bear = bar["h4_close"] < bar["h4_ema"]

                bull_sweep = (bar["low"] < bar["swing_low"]) and (bar["close"] > bar["swing_low"]) and (bar["close"] > bar["open"])
                bear_sweep = (bar["high"] > bar["swing_high"]) and (bar["close"] < bar["swing_high"]) and (bar["close"] < bar["open"])

                long_sig = h4_bull and bull_sweep and (bar["low"] <= bar["vwap_lower"]) and (bar["vwrsi"] < 46) and (bar["vwrsi"] > prev["vwrsi"])
                short_sig = h4_bear and bear_sweep and (bar["high"] >= bar["vwap_upper"]) and (bar["vwrsi"] > 54) and (bar["vwrsi"] < prev["vwrsi"])

                atr_val = float(bar["atr"])
                sl_dist = atr_val * SL_ATR_MULT
                tp_dist = atr_val * TP_ATR_MULT
                risk_cash = equity * (RISK_PER_TRADE_PCT / 100.0)
                entry_p = float(bar["close"])

                if sl_dist > 0 and (long_sig or short_sig):
                    oz = risk_cash / sl_dist
                    comm = oz * COMMISSION_PER_OZ * 2
                    trades_today += 1
                    if long_sig:
                        pos = {
                            "type": "LONG", "entry": entry_p, "entry_time": now_ts,
                            "entry_str": dt.strftime("%Y-%m-%d %H:%M"), "entry_hour": dt.hour,
                            "sl": entry_p - sl_dist, "tp": entry_p + tp_dist,
                            "be_trigger": entry_p + (sl_dist * BE_TRIGGER_R),
                            "oz": oz, "comm": comm, "atr": atr_val, "is_be": False
                        }
                    else:
                        pos = {
                            "type": "SHORT", "entry": entry_p, "entry_time": now_ts,
                            "entry_str": dt.strftime("%Y-%m-%d %H:%M"), "entry_hour": dt.hour,
                            "sl": entry_p + sl_dist, "tp": entry_p - tp_dist,
                            "be_trigger": entry_p - (sl_dist * BE_TRIGGER_R),
                            "oz": oz, "comm": comm, "atr": atr_val, "is_be": False
                        }

        if i % 4 == 0:
            equity_curve.append({"time": now_ts, "value": round(equity, 2)})

    pd.DataFrame(closed_trades).to_csv(TRADES_CSV, index=False)

    start_bday = (df.iloc[start_idx]["datetime"] + pd.Timedelta(hours=7)).date()
    end_bday = (df.iloc[-1]["datetime"] + pd.Timedelta(hours=7)).date()
    total_mon_fri_days = max(1, len(pd.bdate_range(start=start_bday, end=end_bday)))

    total_trades = len(closed_trades)
    winners = [t for t in closed_trades if t["pnl"] > 0]
    losers = [t for t in closed_trades if t["pnl"] <= 0]
    longs = [t for t in closed_trades if t["type"] == "LONG"]
    shorts = [t for t in closed_trades if t["type"] == "SHORT"]

    win_rate = (len(winners) / total_trades * 100.0) if total_trades > 0 else 0.0
    gross_win = sum(t["pnl"] for t in winners)
    gross_loss = abs(sum(t["pnl"] for t in losers))
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else 0.0
    net_pnl = equity - INITIAL_CAPITAL
    net_pnl_pct = (net_pnl / INITIAL_CAPITAL) * 100.0
    avg_daily_pct = net_pnl_pct / total_mon_fri_days

    curr = df.iloc[-2]
    prev = df.iloc[-3]
    in_sess_now = is_open_thai_market(curr["datetime"])
    h4_bull_now = (curr["h4_close"] >= curr["h4_ema"]) if not pd.isna(curr["h4_ema"]) else True

    sig_type = "WAIT"
    entry_now = float(curr["close"])
    atr_now = float(curr["atr"]) if not pd.isna(curr["atr"]) else 1.0
    sl_d = atr_now * SL_ATR_MULT
    tp_d = atr_now * TP_ATR_MULT
    lot_now = round((equity * (RISK_PER_TRADE_PCT / 100.0)) / (sl_d * 100.0), 2) if sl_d > 0 else 0.0

    if in_sess_now and not pd.isna(curr["swing_low"]):
        bull_s = (curr["low"] < curr["swing_low"]) and (curr["close"] > curr["swing_low"]) and (curr["close"] > curr["open"])
        bear_s = (curr["high"] > curr["swing_high"]) and (curr["close"] < curr["swing_high"]) and (curr["close"] < curr["open"])
        if h4_bull_now and bull_s and (curr["low"] <= curr["vwap_lower"]) and (curr["vwrsi"] < 46) and (curr["vwrsi"] > prev["vwrsi"]):
            sig_type = "LONG"
        elif (not h4_bull_now) and bear_s and (curr["high"] >= curr["vwap_upper"]) and (curr["vwrsi"] > 54) and (curr["vwrsi"] < prev["vwrsi"]):
            sig_type = "SHORT"

    candles = [
        {"time": int(r["ts"]), "open": round(float(r["open"]), 2), "high": round(float(r["high"]), 2), "low": round(float(r["low"]), 2), "close": round(float(r["close"]), 2)}
        for _, r in df.tail(300).iterrows()
    ]

    def clean_num(val):
        return 0.0 if (val is None or (isinstance(val, float) and math.isnan(val))) else round(float(val), 3)

    h4_txt = "H4 BULL ONLY" if h4_bull_now else "H4 BEAR ONLY"
    regime_label = f"{h4_txt} | VWAP ${round(float(curr['vwap']), 1)} | VWRSI {round(float(curr['vwrsi']), 1)}" if not pd.isna(curr["vwap"]) else h4_txt

    state = {
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "data_source": source_name,
        "history_range": f"{df.iloc[0]['datetime'].strftime('%Y-%m-%d')} ถึง {df.iloc[-1]['datetime'].strftime('%Y-%m-%d')} ({total_mon_fri_days} วันทำการ)",
        "current_price": round(float(df.iloc[-1]["close"]), 2),
        "macro_z": clean_num(curr["macro_z"]),
        "fast_z": clean_num(curr["fast_z"]),
        "atr": round(atr_now, 2),
        "regime": regime_label,
        "signal": {
            "type": sig_type,
            "entry": round(entry_now, 2) if sig_type != "WAIT" else None,
            "sl": round(entry_now - sl_d if sig_type == "LONG" else entry_now + sl_d, 2) if sig_type != "WAIT" else None,
            "tp": round(entry_now + tp_d if sig_type == "LONG" else entry_now - tp_d, 2) if sig_type != "WAIT" else None,
            "be_trigger": round(entry_now + sl_d * BE_TRIGGER_R if sig_type == "LONG" else entry_now - sl_d * BE_TRIGGER_R, 2) if sig_type != "WAIT" else None,
            "lot_size": lot_now
        },
        "backtest": {
            "net_pnl": round(net_pnl, 2),
            "net_pnl_pct": round(net_pnl_pct, 2),
            "avg_daily_pct": round(avg_daily_pct, 3),
            "max_dd_pct": round(max_dd_pct, 2),
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "days_hit_target": days_hit_target,
            "long_pnl": round(sum(t["pnl"] for t in longs), 2),
            "short_pnl": round(sum(t["pnl"] for t in shorts), 2),
            "recent_trades": closed_trades[-15:][::-1],
            "equity_curve": equity_curve
        },
        "candles": candles
    }
    return state

if __name__ == "__main__":
    df, source_name = fetch_and_store_history()
    state = run_quant_backtest(df, source_name)
    with open("data/state.json", "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, allow_nan=False)
    print(f"V8.1 Complete | Mon-Fri Avg: {state['backtest']['avg_daily_pct']}%/day | Net PnL: ${state['backtest']['net_pnl']} | PF: {state['backtest']['profit_factor']}")
