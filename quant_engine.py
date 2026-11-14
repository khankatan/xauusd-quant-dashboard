import os
import json
import math
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from engine.config import INITIAL_CAPITAL, SL_ATR_MULT, TP_ATR_MULT, BE_TRIGGER_R, TRADES_CSV, STATE_JSON
from engine.data_feed import fetch_market_data
from engine.indicators import compute_all_features
from engine.strategy_brain import evaluate_signals
from engine.risk_manager import RiskGuard

os.makedirs("data", exist_ok=True)

def run_modular_engine():
    df, source_name = fetch_market_data()
    df = compute_all_features(df)

    guard = RiskGuard(INITIAL_CAPITAL)
    asian_high = -np.inf
    asian_low = np.inf
    asian_bars = 0
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

        dt = bar["datetime"]
        bar_date = bar["thai_date"]
        now_ts = int(bar["ts"])
        t_mins = int(bar["thai_mins"])

        if last_date != bar_date:
            last_date = bar_date
            asian_high = -np.inf
            asian_low = np.inf
            asian_bars = 0

        if (8 * 60) <= t_mins <= (13 * 60 + 45):
            asian_high = max(asian_high, float(bar["high"]))
            asian_low = min(asian_low, float(bar["low"]))
            asian_bars += 1

        guard.on_new_bar(bar_date)

        # บริหารออเดอร์ที่เปิดอยู่
        if pos is not None:
            exit_price = None
            exit_reason = None

            if pos["type"] == "LONG":
                if not pos["is_be"] and bar["high"] >= pos["be_trigger"]:
                    pos["sl"] = pos["entry"] + (pos["atr"] * 0.08)
                    pos["is_be"] = True
                if bar["low"] <= pos["sl"]:
                    exit_price = pos["sl"]
                    exit_reason = f"{pos['agent']}-BE+" if pos["is_be"] else f"{pos['agent']}-SL"
                elif bar["high"] >= pos["tp"]:
                    exit_price = pos["tp"]
                    exit_reason = f"{pos['agent']}-TP"
                elif bar["thai_hour"] == 2 and bar["thai_minute"] >= 30:
                    exit_price = float(bar["close"])
                    exit_reason = "Rollover"

                if exit_price is not None:
                    net_pnl = ((exit_price - pos["entry"]) * pos["oz"]) - pos["comm"]
                    guard.record_close(net_pnl, exit_reason)
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
                    pos["sl"] = pos["entry"] - (pos["atr"] * 0.08)
                    pos["is_be"] = True
                if bar["high"] >= pos["sl"]:
                    exit_price = pos["sl"]
                    exit_reason = f"{pos['agent']}-BE+" if pos["is_be"] else f"{pos['agent']}-SL"
                elif bar["low"] <= pos["tp"]:
                    exit_price = pos["tp"]
                    exit_reason = f"{pos['agent']}-TP"
                elif bar["thai_hour"] == 2 and bar["thai_minute"] >= 30:
                    exit_price = float(bar["close"])
                    exit_reason = "Rollover"

                if exit_price is not None:
                    net_pnl = ((pos["entry"] - exit_price) * pos["oz"]) - pos["comm"]
                    guard.record_close(net_pnl, exit_reason)
                    closed_trades.append({
                        "entry_str": pos["entry_str"], "exit_str": dt.strftime("%Y-%m-%d %H:%M"),
                        "entry_time": pos["entry_time"], "exit_time": now_ts,
                        "entry_hour_utc": pos["entry_hour"], "type": "SHORT",
                        "entry": round(pos["entry"], 2), "exit": round(exit_price, 2),
                        "pnl": round(net_pnl, 2), "reason": exit_reason
                    })
                    pos = None

        # ถามสมองส่วนตัดสินใจหากอวัยวะความเสี่ยงอนุญาตให้เทรด
        if pos is None and guard.can_trade():
            sig_dir, agent_tag = evaluate_signals(bar, prev, asian_high, asian_low, asian_bars)
            if sig_dir is not None:
                pos = guard.build_order(sig_dir, agent_tag, float(bar["close"]), float(bar["atr"]), dt, now_ts)

        if i % 4 == 0:
            equity_curve.append({"time": now_ts, "value": round(guard.equity, 2)})

    pd.DataFrame(closed_trades).to_csv(TRADES_CSV, index=False)

    start_bday = df.iloc[start_idx]["thai_date"]
    end_bday = df.iloc[-1]["thai_date"]
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
    net_pnl = guard.equity - INITIAL_CAPITAL
    net_pnl_pct = (net_pnl / INITIAL_CAPITAL) * 100.0
    avg_daily_pct = net_pnl_pct / total_mon_fri_days

    curr = df.iloc[-2]
    prev = df.iloc[-3]
    sig_now, agent_now = evaluate_signals(curr, prev, asian_high, asian_low, asian_bars)
    sig_type = sig_now if sig_now else "WAIT"

    entry_now = float(curr["close"])
    atr_now = float(curr["atr"]) if not pd.isna(curr["atr"]) else 1.0
    sl_d = atr_now * SL_ATR_MULT
    tp_d = atr_now * TP_ATR_MULT
    lot_now = round((guard.equity * (guard.get_active_risk_pct() / 100.0)) / (sl_d * 100.0), 2) if sl_d > 0 else 0.0

    candles = [
        {"time": int(r["ts"]), "open": round(float(r["open"]), 2), "high": round(float(r["high"]), 2), "low": round(float(r["low"]), 2), "close": round(float(r["close"]), 2)}
        for _, r in df.tail(300).iterrows()
    ]

    def clean_num(val):
        return 0.0 if (val is None or (isinstance(val, float) and math.isnan(val))) else round(float(val), 3)

    h1_txt = "H1 BULL" if curr["h1_close"] >= curr["h1_ema"] else "H1 BEAR"
    regime_label = f"{h1_txt} | VWAP ${round(float(curr['vwap']), 1)} | VWRSI {round(float(curr['vwrsi']), 1)}" if not pd.isna(curr["vwap"]) else h1_txt

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
            "max_dd_pct": round(guard.max_dd_pct, 2),
            "max_daily_dd_pct": round(guard.max_daily_dd_pct, 2),
            "total_trades": total_trades,
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "days_hit_target": guard.days_hit_target,
            "long_pnl": round(sum(t["pnl"] for t in longs), 2),
            "short_pnl": round(sum(t["pnl"] for t in shorts), 2),
            "recent_trades": closed_trades[-15:][::-1],
            "equity_curve": equity_curve
        },
        "candles": candles
    }

    with open(STATE_JSON, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, allow_nan=False)

    print(f"Modular Multi-Brain Complete | Trades: {total_trades}/{total_mon_fri_days}d | Net PnL: ${state['backtest']['net_pnl']} | MaxDD: {state['backtest']['max_dd_pct']}% | MaxDailyDD: {state['backtest']['max_daily_dd_pct']}%")

if __name__ == "__main__":
    run_modular_engine()
