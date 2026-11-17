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
                        exit_reason = f"{tag_prefix}-TP1+StepLock"
                    elif pos["partial_closed"]:
                        exit_reason = f"{tag_prefix}-TP1+BE+"
                    elif pos["is_be"]:
                        exit_reason = f"{tag_prefix}-BE+"
                    else:
                        exit_reason = f"{tag_prefix}-SL"
                else:
                    if (not pos["partial_closed"]) and (float(bar["low"]) <= pos["tp1"]):
                        closed_oz = pos["oz"] * pos["partial_ratio"]
                        pos["rem_oz"] = pos["oz"] - closed_oz
                        pos["partial_pnl"] = ((pos["entry"] - pos["tp1"]) * closed_oz) - (pos["comm"] * pos["partial_ratio"])
                        pos["partial_closed"] = True
                        pos["is_be"] = True
                        pos["sl"] = min(pos["sl"], pos["entry"] - (pos["atr"] * BE_BUFFER_ATR))

                    if (not pos.get("step_locked", False)) and (pos["max_fav_r"] >= STEP_LOCK_TRIGGER_R):
                        pos["step_locked"] = True
                        pos["is_be"] = True
                        step_lock_price = pos["entry"] - (sl_dist * STEP_LOCK_LOCK_R)
                        pos["sl"] = min(pos["sl"], step_lock_price)

                    elif (not pos["is_be"]) and is_late_night and (pos["max_fav_r"] >= LATE_BE_TRIGGER_R):
                        pos["is_be"] = True
                        pos["sl"] = min(pos["sl"], pos["entry"] - (pos["atr"] * BE_BUFFER_ATR))

                    if float(bar["low"]) <= pos["tp"]:
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
                    rem_pnl = ((pos["entry"] - exit_price) * pos["rem_oz"]) - (pos["comm"] * rem_ratio)
                    net_pnl = pos["partial_pnl"] + rem_pnl
                    eff_exit = (pos["tp1"] * pos["partial_ratio"] + exit_price * rem_ratio) if pos["partial_closed"] else exit_price

                    guard.record_close(net_pnl, exit_reason, pos["agent"])
                    guard.on_new_bar(bar_date)
                    closed_trades.append({
                        "entry_str": pos["entry_str"], "exit_str": dt.strftime("%Y-%m-%d %H:%M"),
                        "entry_time": pos["entry_time"], "exit_time": now_ts,
                        "entry_hour_utc": pos["entry_hour"], "type": "SELL",
                        "entry": round(pos["entry"], 2), "exit": round(eff_exit, 2),
                        "pnl": round(net_pnl, 2), "reason": exit_reason
                    })
                    pos = None

        elif (not friday_close_now) and (not daily_rollover_now) and guard.can_trade():
            sig_dir, agent_tag = evaluate_signals(bar, prev, asian_high, asian_low, asian_bars, guard.trades_today, day_open)
            if sig_dir is None:
                sig_dir, agent_tag = evaluate_gap_filler(bar, prev, guard.trades_today, lon_open, lon_close)

            if sig_dir is not None:
                is_conv = bool(bar["macro_bull_conv"]) if sig_dir == "BUY" else bool(bar["macro_bear_conv"])
                atr_val = float(bar["atr"])
                move_open = abs(float(bar["close"]) - day_open) / atr_val if (day_open is not None and atr_val > 0) else 0.0
                pos = guard.build_order(sig_dir, agent_tag, float(bar["close"]), atr_val, dt, now_ts, is_conv, utc_hour=utc_hour, move_from_open_atr=move_open)

        if i % 4 == 0:
            equity_curve.append({"time": now_ts, "value": round(guard.equity, 2)})

    pd.DataFrame(closed_trades).to_csv(TRADES_CSV, index=False)

    start_bday = df.iloc[start_idx]["thai_date"]
    end_bday = df.iloc[-1]["thai_date"]
    total_mon_fri_days = max(1, len(pd.bdate_range(start=start_bday, end=end_bday)))

    total_trades = len(closed_trades)
    winners = [t for t in closed_trades if t["pnl"] > 0]
    losers = [t for t in closed_trades if t["pnl"] <= 0]
    buys = [t for t in closed_trades if t["type"] == "BUY"]
    sells = [t for t in closed_trades if t["type"] == "SELL"]

    def agent_stats(keywords):
        sub = [t for t in closed_trades if any(k in t["reason"] for k in keywords)]
        w = [t for t in sub if t["pnl"] > 0]
        l = [t for t in sub if t["pnl"] <= 0]
        gw = sum(t["pnl"] for t in w)
        gl = abs(sum(t["pnl"] for t in l))
        return {
            "trades": len(sub),
            "win_rate": round((len(w) / len(sub) * 100.0), 1) if sub else 0.0,
            "net_pnl": round(sum(t["pnl"] for t in sub), 2),
            "pf": round((gw / gl), 2) if gl > 0 else (9.99 if gw > 0 else 0.0)
        }

    agents_breakdown = {
        "VWAP_PB": agent_stats(["SWEET"]),
        "EV_PB": agent_stats(["SOUR", "SALTY"]),
        "OI_BOOSTED": agent_stats(["TP1+"]),
        "ROLLOVER": agent_stats(["FLIP-", "GAP-", "Rollover", "Weekend-Close", "Wknd"])
    }

    win_rate = (len(winners) / total_trades * 100.0) if total_trades > 0 else 0.0
    gross_win = sum(t["pnl"] for t in winners)
    gross_loss = abs(sum(t["pnl"] for t in losers))
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else 0.0
    net_pnl = guard.equity - INITIAL_CAPITAL
    net_pnl_pct = (net_pnl / INITIAL_CAPITAL) * 100.0
    avg_daily_pct = net_pnl_pct / total_mon_fri_days

    curr = df.iloc[-2]
    curr_dt = curr["datetime"].to_pydatetime()
    curr_utc_h = int(curr["thai_hour"]) - 7
    if curr_utc_h < 0:
        curr_utc_h += 24

    entry_now = float(curr["close"])
    atr_now = float(curr["atr"]) if not pd.isna(curr["atr"]) else 1.0
    move_open_now = abs(entry_now - day_open) / atr_now if (day_open is not None and atr_now > 0) else 0.0

    # ยึดผลลัพธ์จากตัวแปร pos ในลูป Backtest 100% (ตรงกับ all_trades.csv ทุกไม้ ไม่คำนวณซ้ำซ้อน)
    if pos is not None:
        is_fresh_entry = (pos["entry_time"] == int(curr["ts"]))
        if is_fresh_entry:
            sig_payload = {
                "type": pos["type"],
                "agent": f"{pos['agent']}{pos['conv']} [TP1 50% @ {BE_TRIGGER_R}R]",
                "risk_pct": pos["risk_pct"],
                "entry": round(pos["entry"], 2),
                "sl": round(pos["sl"], 2),
                "tp1": round(pos["tp1"], 2),
                "tp": round(pos["tp"], 2),
                "be_trigger": round(pos["tp1"], 2),
                "lot_size": round(pos["oz"] / 100.0, 2),
                "partial_lot": round((pos["oz"] * pos["partial_ratio"]) / 100.0, 2)
            }
        else:
            status_badge = "🔥 STEP-LOCK / TP1 LOCKED" if pos.get("step_locked", False) else ("🔥 TP1 (50%) LOCKED & BE+ ACTIVE" if pos["partial_closed"] else "⏳ HOLDING FOR TP1 (50%)")
            sig_payload = {
                "type": f"HOLD {pos['type']}",
                "agent": f"{pos['agent']}{pos['conv']} | {status_badge}",
                "risk_pct": pos["risk_pct"],
                "entry": round(pos["entry"], 2),
                "sl": round(pos["sl"], 2),
                "tp1": round(pos["tp1"], 2),
                "tp": round(pos["tp"], 2),
                "be_trigger": round(pos["tp1"], 2),
                "lot_size": round(pos["rem_oz"] / 100.0, 2)
            }
    else:
        sig_payload = {
            "type": "WAIT",
            "agent": "SCANNING (V23.3 FTMO-SCALED DUAL-BRAIN)",
            "risk_pct": guard.get_active_risk_pct(False, "", atr_now, curr_utc_h, move_open_now),
            "entry": None, "sl": None, "tp1": None, "tp": None, "be_trigger": None, "lot_size": 0.0
        }

    candles = [
        {"time": int(r["ts"]), "open": round(float(r["open"]), 2), "high": round(float(r["high"]), 2), "low": round(float(r["low"]), 2), "close": round(float(r["close"]), 2)}
        for _, r in df.tail(300).iterrows()
    ]

    def clean_num(val):
        return 0.0 if (val is None or (isinstance(val, float) and math.isnan(val))) else round(float(val), 3)

    h1_txt = "H1 BULL" if curr["h1_close"] >= curr["h1_ema"] else "H1 BEAR"
    dst_txt = "US-SUMMER (Close 03:00 TH)" if is_us_dst_active(curr_dt) else "US-WINTER (Close 03:00 TH)"
    macro_txt = str(curr["macro_status"]) if "macro_status" in curr else "OI+DXY: STANDARD"
    regime_label = f"{h1_txt} | CHOP: {clean_num(curr.get('chop', 50.0))} | {macro_txt} | {dst_txt}"

    state = {
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "data_source": f"{source_name} + COMEX GC=F OI & DXY (V23.3 FTMO-Scaled Dual-Brain)",
        "history_range": f"{df.iloc[0]['datetime'].strftime('%Y-%m-%d')} ถึง {df.iloc[-1]['datetime'].strftime('%Y-%m-%d')} ({total_mon_fri_days} วันทำการ)",
        "current_price": round(float(df.iloc[-1]["close"]), 2),
        "equity": round(guard.equity, 2),
        "lowest_equity": round(guard.lowest_equity, 2),
        "macro_z": clean_num(curr["macro_z"]),
        "fast_z": clean_num(curr["fast_z"]),
        "atr": round(atr_now, 2),
        "regime": regime_label,
        "signal": sig_payload,
        "backtest": {
            "net_pnl": round(net_pnl, 2),
            "net_pnl_pct": round(net_pnl_pct, 2),
            "avg_daily_pct": round(avg_daily_pct, 3),
            "max_overall_dd_pct": round(guard.max_overall_dd_pct, 2),
            "max_overall_dd_cash": round(guard.max_overall_dd_cash, 2),
            "max_daily_dd_pct": round(guard.max_daily_dd_pct, 2),
            "max_daily_dd_cash": round(guard.max_daily_dd_cash, 2),
            "worst_dd_date": guard.worst_dd_date,
            "total_trades": total_trades,
            "total_bdays": total_mon_fri_days,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "days_hit_target": guard.days_hit_target,
            "buy_pnl": round(sum(t["pnl"] for t in buys), 2),
            "sell_pnl": round(sum(t["pnl"] for t in sells), 2),
            "agents": agents_breakdown,
            "recent_trades": closed_trades[-20:][::-1],
            "equity_curve": equity_curve
        },
        "candles": candles
    }

    with open(STATE_JSON, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, allow_nan=False)

    print(f"V23.3 Complete | Net PnL: ${state['backtest']['net_pnl']} | PF: {state['backtest']['profit_factor']} | WR: {state['backtest']['win_rate']}% | MaxOverallDD: {state['backtest']['max_overall_dd_pct']}%")

if __name__ == "__main__":
    run_modular_engine()
