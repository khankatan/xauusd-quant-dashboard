import os
import json
import math
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from engine.config import (
    INITIAL_CAPITAL, SL_ATR_MULT, TP_ATR_MULT, BE_TRIGGER_R,
    PARTIAL_TP_RATIO, BE_BUFFER_ATR, LATE_BE_TRIGGER_R,
    STEP_LOCK_TRIGGER_R, STEP_LOCK_LOCK_R, TRADES_CSV, STATE_JSON
)
from engine.data_feed import fetch_market_data
from engine.indicators import compute_all_features
from engine.macro_oi import fetch_macro_oi_and_dxy
from engine.strategy_brain import evaluate_signals
from engine.gap_filler_engine import evaluate_gap_filler
from engine.risk_manager import RiskGuard, get_agent_sl_tp_mult

os.makedirs("data", exist_ok=True)

def is_us_dst_active(utc_dt):
    year = utc_dt.year
    mar_first = datetime(year, 3, 1, tzinfo=timezone.utc)
    mar_second_sun = 1 + ((6 - mar_first.weekday()) % 7) + 7
    dst_start = datetime(year, 3, mar_second_sun, 7, 0, tzinfo=timezone.utc)

    nov_first = datetime(year, 11, 1, tzinfo=timezone.utc)
    nov_first_sun = 1 + ((6 - nov_first.weekday()) % 7)
    dst_end = datetime(year, 11, nov_first_sun, 6, 0, tzinfo=timezone.utc)

    return dst_start <= utc_dt < dst_end

def must_close_for_weekend(utc_dt):
    wd = utc_dt.weekday()
    if wd >= 5:
        return True
    if wd == 4 and utc_dt.hour >= 20:
        return True
    return False

def run_modular_engine():
    df, source_name = fetch_market_data()
    df = compute_all_features(df)
    df = fetch_macro_oi_and_dxy(df)

    guard = RiskGuard(INITIAL_CAPITAL)
    asian_high = -np.inf
    asian_low = np.inf
    asian_bars = 0
    lon_open = None
    lon_close = None
    day_open = None
    last_date = None

    pos = None
    closed_trades = []
    equity_curve = []

    start_idx = 105
    for i in range(start_idx, len(df) - 1):
        bar = df.iloc[i]
        prev = df.iloc[i - 1]
        if pd.isna(bar["vwap"]) or pd.isna(bar["vwrsi"]) or pd.isna(bar["atr"]) or pd.isna(bar["h1_ema"]):
            continue

        dt = bar["datetime"].to_pydatetime()
        bar_date = bar["thai_date"]
        now_ts = int(bar["ts"])
        t_mins = int(bar["thai_mins"])
        utc_hour = int(bar["thai_hour"]) - 7
        if utc_hour < 0:
            utc_hour += 24

        if last_date != bar_date:
            last_date = bar_date
            asian_high = -np.inf
            asian_low = np.inf
            asian_bars = 0
            lon_open = None
            lon_close = None
            day_open = float(bar["open"])

        if (8 * 60) <= t_mins <= (13 * 60 + 45):
            asian_high = max(asian_high, float(bar["high"]))
            asian_low = min(asian_low, float(bar["low"]))
            asian_bars += 1

        if 7 <= utc_hour <= 12:
            if lon_open is None:
                lon_open = float(bar["open"])
            lon_close = float(bar["close"])

        guard.on_new_bar(bar_date)

        friday_close_now = must_close_for_weekend(dt)
        daily_rollover_now = (int(bar["thai_hour"]) == 3 and int(bar["thai_minute"]) >= 0)
        is_late_night = (t_mins >= 23 * 60 + 30) or (t_mins < 3 * 60)

        if pos is not None:
            exit_price = None
            exit_reason = None
            sl_dist = pos.get("sl_dist", pos["atr"] * SL_ATR_MULT)
            tag_prefix = f"{pos['agent']}{pos['conv']}"

            gap_intraday_exit = (("GAP-" in pos["agent"]) or ("FLIP-" in pos["agent"])) and (int(bar["thai_hour"]) == 2 and int(bar["thai_minute"]) >= 30)

            if pos["type"] == "BUY":
                fav_r = (float(bar["high"]) - pos["entry"]) / sl_dist if sl_dist > 0 else 0.0
                pos["max_fav_r"] = max(pos.get("max_fav_r", 0.0), fav_r)

                if float(bar["low"]) <= pos["sl"]:
                    exit_price = pos["sl"]
                    if pos.get("step_locked", False):
                        exit_reason = f"{tag_prefix}-TP1+StepLock"
                    elif pos["partial_closed"]:
                        exit_reason = f"{tag_prefix}-TP1+BE+"
                    elif pos["is_be"]:
                        exit_reason = f"{tag_prefix}-BE+"
                    else:
                        exit_reason = f"{tag_prefix}-SL"
                else:
                    if (not pos["partial_closed"]) and (float(bar["high"]) >= pos["tp1"]):
                        closed_oz = pos["oz"] * pos["partial_ratio"]
                        pos["rem_oz"] = pos["oz"] - closed_oz
                        pos["partial_pnl"] = ((pos["tp1"] - pos["entry"]) * closed_oz) - (pos["comm"] * pos["partial_ratio"])
                        pos["partial_closed"] = True
                        pos["is_be"] = True
                        pos["sl"] = max(pos["sl"], pos["entry"] + (pos["atr"] * BE_BUFFER_ATR))

                    if (not pos.get("step_locked", False)) and (pos["max_fav_r"] >= STEP_LOCK_TRIGGER_R):
                        pos["step_locked"] = True
                        pos["is_be"] = True
                        step_lock_price = pos["entry"] + (sl_dist * STEP_LOCK_LOCK_R)
                        pos["sl"] = max(pos["sl"], step_lock_price)

                    elif (not pos["is_be"]) and is_late_night and (pos["max_fav_r"] >= LATE_BE_TRIGGER_R):
                        pos["is_be"] = True
                        pos["sl"] = max(pos["sl"], pos["entry"] + (pos["atr"] * BE_BUFFER_ATR))

                    if float(bar["high"]) >= pos["tp"]:
                        exit_price = pos["tp"]
                        exit_reason = f"{tag_prefix}-TP1+TP2" if pos["partial_closed"] else f"{tag_prefix}-TP"
                    elif gap_intraday_exit:
                        exit_price = float(bar["close"])
                        exit_reason = f"{tag_prefix}-TP1+EOD" if pos["partial_closed"] else f"{tag_prefix}-EOD"
                    elif friday_close_now:
                        exit_price = float(bar["close"])
                        exit_reason = f"{tag_prefix}-TP1+Wknd" if pos["partial_closed"] else "Weekend-Close"
                    elif daily_rollover_now:
                        exit_price = float(bar["close"])
                        exit_reason = f"{tag_prefix}-TP1+Rollover" if pos["partial_closed"] else "Rollover"

                if exit_price is not None:
                    rem_ratio = pos["rem_oz"] / pos["oz"] if pos["oz"] > 0 else 1.0
                    rem_pnl = ((exit_price - pos["entry"]) * pos["rem_oz"]) - (pos["comm"] * rem_ratio)
                    net_pnl = pos["partial_pnl"] + rem_pnl
                    eff_exit = (pos["tp1"] * pos["partial_ratio"] + exit_price * rem_ratio) if pos["partial_closed"] else exit_price

                    guard.record_close(net_pnl, exit_reason, pos["agent"])
                    guard.on_new_bar(bar_date)
                    closed_trades.append({
                        "entry_str": pos["entry_str"], "exit_str": dt.strftime("%Y-%m-%d %H:%M"),
                        "entry_time": pos["entry_time"], "exit_time": now_ts,
                        "entry_hour_utc": pos["entry_hour"], "type": "BUY",
                        "entry": round(pos["entry"], 2), "exit": round(eff_exit, 2),
                        "pnl": round(net_pnl, 2), "reason": exit_reason
                    })
                    pos = None

            elif pos["type"] == "SELL":
                fav_r = (pos["entry"] - float(bar["low"])) / sl_dist if sl_dist > 0 else 0.0
                pos["max_fav_r"] = max(pos.get("max_fav_r", 0.0), fav_r)

                if float(bar["high"]) >= pos["sl"]:
                    exit_price = pos["sl"]
                    if pos.get("step_locked", False):
                        exit_reason = f"{tag_prefix}-TP1+Step
