import os
import json
import math
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

INITIAL_CAPITAL = 100000.0
RISK_PER_TRADE_PCT = 0.25
MAX_2HR_RISK_PCT = 1.00
DAILY_TARGET_PCT = 0.30
HARD_DAILY_DD_PCT = 4.50
COMMISSION_PER_OZ = 0.035

MACRO_Z_LEN = 100
FAST_Z_LEN = 14
ATR_LEN = 14
SL_ATR_MULT = 2.0
TP_ATR_MULT = 4.5
BE_TRIGGER_R = 1.5

os.makedirs("data", exist_ok=True)
HISTORY_CSV = "data/xauusd_m15_history.csv"
TRADES_CSV = "data/all_trades.csv"

def to_unix_seconds(series):
    # แปลงเวลาเป็นวินาทีเต็ม 10 หลักอย่างแม่นยำ ป้องกันตัวเลขเพี้ยน
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
            source_name = "TwelveData Spot XAU/USD (5,000 Bars)"
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
    combined["source"] = source_name
    combined.to_csv(HISTORY_CSV, index=False)
    return combined, source_name

def run_quant_backtest(df, source_name):
    df = df.copy()
    df["macro_mean"] = df["close"].rolling(MACRO_Z_LEN).mean()
    df["macro_std"] = df["close"].rolling(MACRO_Z_LEN).std()
    df["macro_z"] = (df["close"] - df["macro_mean"]) / df["macro_std"].replace(0, np.nan)

    df["fast_mean"] = df["close"].rolling(FAST_Z_LEN).mean()
    df["fast_std"] = df["close"].rolling(FAST_Z_LEN).std()
    df["fast_z"] = (df["close"] - df["fast_mean"]) / df["fast_std"].replace(0, np.nan)

    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift(1))
    low_close = np.abs(df["low"] - df["close"].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr"] = tr.rolling(ATR_LEN).mean()

    equity = INITIAL_CAPITAL
    peak_equity = INITIAL_CAPITAL
    max_dd_pct = 0.0

    current_day = None
    daily_start_eq = INITIAL_CAPITAL
    daily_high_water = INITIAL_CAPITAL
    days_hit_target = 0
    today_target_logged = False

    pos = None
    closed_trades = []
    equity_curve = []

    start_idx = MACRO_Z_LEN + 5
    for i in range(start_idx, len(df) - 1):
        bar = df.iloc[i]
        prev = df.iloc[i - 1]
        macro_prev2 = df.iloc[i - 2]["macro_z"]

        if pd.isna(bar["macro_z"]) or pd.isna(bar["fast_z"]) or pd.isna(bar["atr"]) or pd.isna(macro_prev2):
            continue

        dt = bar["datetime"]
        bar_date = dt.date()
        now_ts = int(bar["ts"])  # วินาทีเต็ม 10 หลัก

        if current_day != bar_date:
            current_day = bar_date
            daily_start_eq = equity
            daily_high_water = equity
            today_target_logged = False

        if pos is not None:
            exit_price = None
            exit_reason = None

            if pos["type"] == "LONG":
                if not pos["is_be"] and bar["high"] >= pos["be_trigger"]:
                    pos["sl"] = pos["entry"] + (pos["atr"] * 0.1)
                    pos["is_be"] = True
                if bar["low"] <= pos["sl"]:
                    exit_price = pos["sl"]
                    exit_reason = "BE+" if pos["is_be"] else "SL"
                elif bar["high"] >= pos["tp"]:
                    exit_price = pos["tp"]
                    exit_reason = "TP"
                elif dt.hour == 20 and dt.minute >= 45:
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
                    exit_reason = "BE+" if pos["is_be"] else "SL"
                elif bar["low"] <= pos["tp"]:
                    exit_price = pos["tp"]
                    exit_reason = "TP"
                elif dt.hour == 20 and dt.minute >= 45:
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

        daily_high_water = max(daily_high_water, equity)
        daily_dd = ((daily_high_water - equity) / daily_high_water) * 100.0
        daily_pnl_pct = ((equity - daily_start_eq) / daily_start_eq) * 100.0

        is_daily_target_hit = daily_pnl_pct >= DAILY_TARGET_PCT
        if is_daily_target_hit and not today_target_logged:
            days_hit_target += 1
            today_target_logged = True

        if pos is None and not is_daily_target_hit and daily_dd < HARD_DAILY_DD_PCT:
            # ตรวจสอบความเสี่ยงสะสมใน 2 ชั่วโมง (7,200 วินาทีจริง)
            used_2hr_money = sum(abs(t["pnl"]) for t in closed_trades[-10:] if (now_ts - t["exit_time"]) <= 7200 and t["pnl"] < 0)
            used_2hr_pct = (used_2hr_money / equity) * 100.0

            in_session = not (20 <= dt.hour <= 22)
            if in_session and (used_2hr_pct + RISK_PER_TRADE_PCT) <= MAX_2HR_RISK_PCT:
                # ฝั่ง Long เข้าไวตามเทรนด์หลัก / ฝั่ง Short ต้องยืนยันแรงขายชัด (macroZ < -0.5)
                is_bull = (bar["macro_z"] > 0.0) and (bar["macro_z"] > macro_prev2)
                is_bear = (bar["macro_z"] < -0.5) and (bar["macro_z"] < macro_prev2)

                long_sig = is_bull and (prev["fast_z"] < -0.35) and (bar["fast_z"] > prev["fast_z"]) and (bar["close"] > bar["open"])
                short_sig = is_bear and (prev["fast_z"] > 0.5) and (bar["fast_z"] < prev["fast_z"]) and (bar["close"] < bar["open"])

                atr_val = float(bar["atr"])
                sl_dist = atr_val * SL_ATR_MULT
                tp_dist = atr_val * TP_ATR_MULT
                risk_cash = equity * (RISK_PER_TRADE_PCT / 100.0)

                if sl_dist > 0 and (long_sig or short_sig):
                    oz = risk_cash / sl_dist
                    comm = oz * COMMISSION_PER_OZ * 2
                    entry_p = float(bar["close"])
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

    curr = df.iloc[-2]
    prev = df.iloc[-3]
    macro_prev2 = df.iloc[-4]["macro_z"]
    is_bull_now = (curr["macro_z"] > 0.0) and (curr["macro_z"] > macro_prev2)
    is_bear_now = (curr["macro_z"] < -0.5) and (curr["macro_z"] < macro_prev2)
    in_sess_now = not (20 <= curr["datetime"].hour <= 22)

    sig_type = "WAIT"
    entry_now = float(curr["close"])
    atr_now = float(curr["atr"]) if not pd.isna(curr["atr"]) else 1.0
    sl_d = atr_now * SL_ATR_MULT
    tp_d = atr_now * TP_ATR_MULT
    lot_now = round((equity * (RISK_PER_TRADE_PCT / 100.0)) / (sl_d * 100.0), 2) if sl_d > 0 else 0.0

    if in_sess_now and is_bull_now and (prev["fast_z"] < -0.35) and (curr["fast_z"] > prev["fast_z"]) and (curr["close"] > curr["open"]):
        sig_type = "LONG"
    elif in_sess_now and is_bear_now and (prev["fast_z"] > 0.5) and (curr["fast_z"] < prev["fast_z"]) and (curr["close"] < curr["open"]):
        sig_type = "SHORT"

    candles = [
        {"time": int(r["ts"]), "open": round(float(r["open"]), 2), "high": round(float(r["high"]), 2), "low": round(float(r["low"]), 2), "close": round(float(r["close"]), 2)}
        for _, r in df.tail(300).iterrows()
    ]

    def clean_num(val):
        return 0.0 if (val is None or (isinstance(val, float) and math.isnan(val))) else round(float(val), 3)

    state = {
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "data_source": source_name,
        "history_range": f"{df.iloc[0]['datetime'].strftime('%Y-%m-%d')} ถึง {df.iloc[-1]['datetime'].strftime('%Y-%m-%d')} ({len(df)} แท่ง)",
        "current_price": round(float(df.iloc[-1]["close"]), 2),
        "macro_z": clean_num(curr["macro_z"]),
        "fast_z": clean_num(curr["fast_z"]),
        "atr": round(atr_now, 2),
        "regime": "BULLISH" if is_bull_now else ("BEARISH" if is_bear_now else "NEUTRAL"),
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
    print(f"Audit Complete | Bars: {len(df)} | Trades: {state['backtest']['total_trades']} | Long PnL: ${state['backtest']['long_pnl']} | Short PnL: ${state['backtest']['short_pnl']}")
