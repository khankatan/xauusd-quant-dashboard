import os
import json
import math
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

INITIAL_CAPITAL = 100000.0
RISK_PER_TRADE_PCT = 0.25     # เสี่ยงคงที่ 0.25% ต่อไม้
DAILY_TARGET_PCT = 0.25       # กำไรถึง +0.25% ของวัน -> ล็อกกำไรหยุดเทรดทันที
MAX_TRADES_PER_DAY = 2        # จำกัดไม่เกิน 2 ไม้/วัน (คุมความเสี่ยงสูงสุดไม่เกิน -0.50%/วัน)
COMMISSION_PER_OZ = 0.035

# พารามิเตอร์ตรวจจับสภาวะตลาด (Regime Detection)
H1_EMA_LEN = 34
H1_ADX_THRESHOLD = 22.0       # ADX > 22 = โหมดเทรนด์ | ADX <= 22 = โหมดไซด์เวย์

# พารามิเตอร์โหมด Trend & Sideways
M15_BREAKOUT_LEN = 12
BB_LEN = 20
BB_STD = 2.0
ATR_LEN = 14

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
            source_name = "TwelveData Spot XAU/USD (Dual-Regime)"
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

def is_clean_thai_session(utc_dt):
    thai_hour = (utc_dt.hour + 7) % 24
    # ตัดเฉพาะช่วง 02:00-07:59 น. (ตลาดปิด/เปิดเอเชีย) และ 20:00-20:59 น. (ข่าวผันผวนแรง)
    if (2 <= thai_hour <= 7) or (thai_hour == 20):
        return False
    return True

def calc_adx(df_h, period=14):
    high, low, close = df_h["high"], df_h["low"], df_h["close"]
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    plus_dm = np.where(plus_dm > minus_dm, plus_dm, 0.0)
    minus_dm = np.where(minus_dm > plus_dm, minus_dm, 0.0)

    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df_h.index).ewm(alpha=1/period, adjust=False).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (pd.Series(minus_dm, index=df_h.index).ewm(alpha=1/period, adjust=False).mean() / atr.replace(0, np.nan))
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    return dx.ewm(alpha=1/period, adjust=False).mean()

def build_dual_regime_features(df):
    df = df.copy()
    # 1. สร้างแท่งเทียน H1 เพื่อตรวจจับสภาวะตลาด (Regime)
    df_h1 = df.set_index("datetime").resample("1h").agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).dropna()

    df_h1["h1_ema"] = df_h1["close"].ewm(span=H1_EMA_LEN, adjust=False).mean()
    df_h1["h1_adx"] = calc_adx(df_h1, 14)

    delta_h1 = df_h1["close"].diff()
    gain_h1 = delta_h1.clip(lower=0).rolling(14).mean()
    loss_h1 = (-delta_h1.clip(upper=0)).rolling(14).mean()
    df_h1["h1_rsi"] = 100 - (100 / (1 + (gain_h1 / loss_h1.replace(0, np.nan))))

    # เลื่อนข้อมูล H1 ไป 1 แท่งเต็ม (ใช้เฉพาะแท่ง H1 ที่ปิดสมบูรณ์แล้ว 100%)
    df_h1_shifted = df_h1[["close", "h1_ema", "h1_adx", "h1_rsi"]].shift(1).rename(columns={"close": "h1_close"})
    df["h1_bucket"] = df["datetime"].dt.floor("1h")
    df = df.merge(df_h1_shifted, left_on="h1_bucket", right_index=True, how="left")

    # 2. Indicator บน M15 สำหรับโหมด Trend & Sideways
    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift(1)).abs(), (df["low"] - df["close"].shift(1)).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(ATR_LEN).mean()

    # โหมด Trend: กรอบ Breakout 12 แท่ง
    df["donchian_high"] = df["high"].rolling(M15_BREAKOUT_LEN).max().shift(1)
    df["donchian_low"] = df["low"].rolling(M15_BREAKOUT_LEN).min().shift(1)

    # โหมด Sideways: Bollinger Bands (20, 2.0) + M15 RSI (14)
    df["bb_mid"] = df["close"].rolling(BB_LEN).mean()
    bb_std = df["close"].rolling(BB_LEN).std()
    df["bb_upper"] = df["bb_mid"] + (BB_STD * bb_std)
    df["bb_lower"] = df["bb_mid"] - (BB_STD * bb_std)

    delta_m15 = df["close"].diff()
    gain_m15 = delta_m15.clip(lower=0).rolling(14).mean()
    loss_m15 = (-delta_m15.clip(upper=0)).rolling(14).mean()
    df["m15_rsi"] = 100 - (100 / (1 + (gain_m15 / loss_m15.replace(0, np.nan))))

    # Z-Score สำหรับ Dashboard
    m100 = df["close"].rolling(100).mean()
    s100 = df["close"].rolling(100).std()
    df["macro_z"] = (df["close"] - m100) / s100.replace(0, np.nan)
    m14 = df["close"].rolling(14).mean()
    s14 = df["close"].rolling(14).std()
    df["fast_z"] = (df["close"] - m14) / s14.replace(0, np.nan)

    return df

def run_quant_backtest(df, source_name):
    df = build_dual_regime_features(df)

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

    start_idx = 150
    for i in range(start_idx, len(df) - 1):
        bar = df.iloc[i]
        prev = df.iloc[i - 1]
        if pd.isna(bar["h1_adx"]) or pd.isna(bar["atr"]) or pd.isna(bar["bb_upper"]) or pd.isna(bar["m15_rsi"]):
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
                    exit_reason = f"{pos['mode']}-BE+" if pos["is_be"] else f"{pos['mode']}-SL"
                elif bar["high"] >= pos["tp"]:
                    exit_price = pos["tp"]
                    exit_reason = f"{pos['mode']}-TP"
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
                    exit_reason = f"{pos['mode']}-BE+" if pos["is_be"] else f"{pos['mode']}-SL"
                elif bar["low"] <= pos["tp"]:
                    exit_price = pos["tp"]
                    exit_reason = f"{pos['mode']}-TP"
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
            if is_clean_thai_session(dt):
                is_trend_regime = bar["h1_adx"] > H1_ADX_THRESHOLD
                atr_val = float(bar["atr"])
                risk_cash = equity * (RISK_PER_TRADE_PCT / 100.0)
                entry_p = float(bar["close"])

                sig_dir = None
                mode_name = ""
                sl_dist = 0.0
                tp_dist = 0.0
                be_r = 1.5

                if is_trend_regime:
                    # === โหมด 1: TREND MODE (H1 Trend + M15 Breakout) ===
                    mode_name = "TREND"
                    h1_bull = (bar["h1_close"] > bar["h1_ema"]) and (bar["h1_rsi"] > 52)
                    h1_bear = (bar["h1_close"] < bar["h1_ema"]) and (bar["h1_rsi"] < 48)
                    if h1_bull and (bar["close"] > bar["donchian_high"]) and (bar["close"] > bar["open"]):
                        sig_dir = "LONG"
                    elif h1_bear and (bar["close"] < bar["donchian_low"]) and (bar["close"] < bar["open"]):
                        sig_dir = "SHORT"
                    sl_dist = atr_val * 2.0
                    tp_dist = atr_val * 4.0
                    be_r = 1.5
                else:
                    # === โหมด 2: SIDEWAYS MODE (BB Mean-Reversion + RSI Divergence/Reversal) ===
                    mode_name = "RANGE"
                    # ราคาลงไปแตะ/หลุดกรอบล่าง BB แล้วกลับตัวปิดแท่งเขียว + RSI Oversold (< 35)
                    if (prev["low"] <= prev["bb_lower"] or bar["low"] <= bar["bb_lower"]) and (prev["m15_rsi"] < 35) and (bar["close"] > bar["open"]):
                        sig_dir = "LONG"
                    # ราคาพุ่งไปแตะ/ทะลุกรอบบน BB แล้วกลับตัวปิดแท่งแดง + RSI Overbought (> 65)
                    elif (prev["high"] >= prev["bb_upper"] or bar["high"] >= bar["bb_upper"]) and (prev["m15_rsi"] > 65) and (bar["close"] < bar["open"]):
                        sig_dir = "SHORT"
                    sl_dist = atr_val * 1.6
                    tp_dist = atr_val * 2.2
                    be_r = 1.1

                if sig_dir is not None and sl_dist > 0:
                    oz = risk_cash / sl_dist
                    comm = oz * COMMISSION_PER_OZ * 2
                    trades_today += 1
                    if sig_dir == "LONG":
                        pos = {
                            "type": "LONG", "mode": mode_name, "entry": entry_p, "entry_time": now_ts,
                            "entry_str": dt.strftime("%Y-%m-%d %H:%M"), "entry_hour": dt.hour,
                            "sl": entry_p - sl_dist, "tp": entry_p + tp_dist,
                            "be_trigger": entry_p + (sl_dist * be_r),
                            "oz": oz, "comm": comm, "atr": atr_val, "is_be": False
                        }
                    else:
                        pos = {
                            "type": "SHORT", "mode": mode_name, "entry": entry_p, "entry_time": now_ts,
                            "entry_str": dt.strftime("%Y-%m-%d %H:%M"), "entry_hour": dt.hour,
                            "sl": entry_p + sl_dist, "tp": entry_p - tp_dist,
                            "be_trigger": entry_p - (sl_dist * be_r),
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

    # สถานะปัจจุบัน (Live Signal)
    curr = df.iloc[-2]
    prev = df.iloc[-3]
    is_trend_now = (curr["h1_adx"] > H1_ADX_THRESHOLD) if not pd.isna(curr["h1_adx"]) else False
    in_sess_now = is_clean_thai_session(curr["datetime"])

    sig_type = "WAIT"
    entry_now = float(curr["close"])
    atr_now = float(curr["atr"]) if not pd.isna(curr["atr"]) else 1.0
    sl_d = atr_now * (2.0 if is_trend_now else 1.6)
    tp_d = atr_now * (4.0 if is_trend_now else 2.2)
    be_r_now = 1.5 if is_trend_now else 1.1
    lot_now = round((equity * (RISK_PER_TRADE_PCT / 100.0)) / (sl_d * 100.0), 2) if sl_d > 0 else 0.0

    if in_sess_now:
        if is_trend_now:
            h1_bull_now = (curr["h1_close"] > curr["h1_ema"]) and (curr["h1_rsi"] > 52)
            h1_bear_now = (curr["h1_close"] < curr["h1_ema"]) and (curr["h1_rsi"] < 48)
            if h1_bull_now and (curr["close"] > curr["donchian_high"]) and (curr["close"] > curr["open"]):
                sig_type = "LONG"
            elif h1_bear_now and (curr["close"] < curr["donchian_low"]) and (curr["close"] < curr["open"]):
                sig_type = "SHORT"
        else:
            if (prev["low"] <= prev["bb_lower"] or curr["low"] <= curr["bb_lower"]) and (prev["m15_rsi"] < 35) and (curr["close"] > curr["open"]):
                sig_type = "LONG"
            elif (prev["high"] >= prev["bb_upper"] or curr["high"] >= curr["bb_upper"]) and (prev["m15_rsi"] > 65) and (curr["close"] < curr["open"]):
                sig_type = "SHORT"

    candles = [
        {"time": int(r["ts"]), "open": round(float(r["open"]), 2), "high": round(float(r["high"]), 2), "low": round(float(r["low"]), 2), "close": round(float(r["close"]), 2)}
        for _, r in df.tail(300).iterrows()
    ]

    def clean_num(val):
        return 0.0 if (val is None or (isinstance(val, float) and math.isnan(val))) else round(float(val), 3)

    regime_label = f"TREND (ADX {round(float(curr['h1_adx']),1)})" if is_trend_now else f"SIDEWAYS (ADX {round(float(curr['h1_adx']),1)})"

    state = {
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "data_source": source_name,
        "history_range": f"{df.iloc[0]['datetime'].strftime('%Y-%m-%d')} ถึง {df.iloc[-1]['datetime'].strftime('%Y-%m-%d')} ({len(df)} แท่ง)",
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
            "be_trigger": round(entry_now + sl_d * be_r_now if sig_type == "LONG" else entry_now - sl_d * be_r_now, 2) if sig_type != "WAIT" else None,
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
    print(f"Dual-Regime V6 Complete | Bars: {len(df)} | Trades: {state['backtest']['total_trades']} | Net PnL: ${state['backtest']['net_pnl']} | PF: {state['backtest']['profit_factor']}")
