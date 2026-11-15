import numpy as np
from engine.config import (
    INITIAL_CAPITAL, BASE_RISK_PCT, CONVICTION_RISK_PCT, THROTTLED_RISK_PCT,
    DAILY_TARGET_PCT, HARD_DAILY_DD_PCT, MAX_TRADES_PER_DAY, STOP_ON_BE_PLUS,
    HOUSE_MONEY_MODE, SL_ATR_MULT, TP_ATR_MULT, BE_TRIGGER_R, COMMISSION_PER_OZ
)

def compute_structural_sl_tp(direction, agent_tag, entry_price, atr_val, swing_low, swing_high, atr_ratio):
    """
    คำนวณจุดตัดขาดทุนและเป้าหมายกำไรจากโครงสร้างราคาจริง (Swing Structure + Vol-Scaled Buffer)
    ปรับระยะเพดาน SL และ RR Target ให้พอดีกับระยะวิ่งจริงของวัฏจักร M15 (ไม่ตั้งเป้าไกลเกินจนราคาเลี้ยวกลับก่อน)
    """
    vol_scale = float(np.clip(atr_ratio, 0.85, 1.30))

    if "SALTY" in agent_tag:
        buf_mult, min_sl_m, max_sl_m, rr_target = 0.65 * vol_scale, 1.4, 2.0, 1.20
    elif "SOUR" in agent_tag:
        buf_mult, min_sl_m, max_sl_m, rr_target = 0.80 * vol_scale, 1.6, 2.3, 1.40
    else:  # SWEET-TREND
        buf_mult, min_sl_m, max_sl_m, rr_target = 0.85 * vol_scale, 1.6, 2.2, 1.35

    if direction == "BUY":
        raw_struct_sl = float(swing_low) - (atr_val * buf_mult)
        sl_dist = np.clip(entry_price - raw_struct_sl, atr_val * min_sl_m, atr_val * max_sl_m)
    else:
        raw_struct_sl = float(swing_high) + (atr_val * buf_mult)
        sl_dist = np.clip(raw_struct_sl - entry_price, atr_val * min_sl_m, atr_val * max_sl_m)

    tp_dist = sl_dist * rr_target
    return float(sl_dist), float(tp_dist)

class RiskGuard:
    def __init__(self, initial_capital=INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.equity = initial_capital
        self.lowest_equity = initial_capital

        self.max_overall_dd_pct = 0.0
        self.max_overall_dd_cash = 0.0

        self.max_daily_dd_pct = 0.0
        self.max_daily_dd_cash = 0.0
        self.worst_dd_date = "-"

        self.current_day = None
        self.daily_start_eq = initial_capital
        self.days_hit_target = 0
        self.today_target_logged = False
        self.today_loss_locked = False
        self.today_be_locked = False
        self.trades_today = 0
        self.tp_wins_today = 0
        self.consecutive_losses = 0

    def on_new_bar(self, bar_date):
        if self.current_day != bar_date:
            self.current_day = bar_date
            self.daily_start_eq = self.equity
            self.today_target_logged = False
            self.today_loss_locked = False
            self.today_be_locked = False
            self.trades_today = 0
            self.tp_wins_today = 0

        self.lowest_equity = min(self.lowest_equity, self.equity)
        dd_from_initial_cash = max(0.0, self.initial_capital - self.equity)
        dd_from_initial_pct = (dd_from_initial_cash / self.initial_capital) * 100.0
        if dd_from_initial_pct > self.max_overall_dd_pct:
            self.max_overall_dd_pct = dd_from_initial_pct
            self.max_overall_dd_cash = dd_from_initial_cash

        daily_pnl_cash = self.equity - self.daily_start_eq
        daily_pnl_pct = (daily_pnl_cash / self.daily_start_eq) * 100.0

        if daily_pnl_cash < 0:
            daily_loss_pct = abs(daily_pnl_pct)
            daily_loss_cash = abs(daily_pnl_cash)
            if daily_loss_pct > self.max_daily_dd_pct:
                self.max_daily_dd_pct = daily_loss_pct
                self.max_daily_dd_cash = daily_loss_cash
                self.worst_dd_date = str(bar_date)

        if daily_pnl_pct >= DAILY_TARGET_PCT and not self.today_target_logged:
            self.days_hit_target += 1
            self.today_target_logged = True

        if daily_pnl_pct <= -HARD_DAILY_DD_PCT:
            self.today_loss_locked = True

    def can_trade(self):
        if self.today_loss_locked or self.today_be_locked:
            return False
        if self.trades_today == 0:
            return True
        if HOUSE_MONEY_MODE and (self.tp_wins_today == self.trades_today) and (self.trades_today < MAX_TRADES_PER_DAY):
            return True
        return False

    def get_active_risk_pct(self, is_macro_conv=False):
        if self.consecutive_losses >= 2:
            base = THROTTLED_RISK_PCT
        else:
            base = CONVICTION_RISK_PCT if is_macro_conv else BASE_RISK_PCT

        if self.trades_today >= 1:
            return round(base * 0.5, 4)
        return base

    def build_order(self, direction, agent_tag, entry_price, atr_val, dt, now_ts, is_macro_conv=False, swing_low=None, swing_high=None, atr_ratio=1.0):
        s_low = entry_price - atr_val if swing_low is None else float(swing_low)
        s_high = entry_price + atr_val if swing_high is None else float(swing_high)

        sl_dist, tp_dist = compute_structural_sl_tp(
            direction, agent_tag, entry_price, atr_val, s_low, s_high, atr_ratio
        )
        if sl_dist <= 0:
            return None

        risk_pct = self.get_active_risk_pct(is_macro_conv)
        risk_cash = self.equity * (risk_pct / 100.0)
        oz = risk_cash / sl_dist
        comm = oz * COMMISSION_PER_OZ * 2
        self.trades_today += 1

        conv_tag = "+OI" if is_macro_conv else ""
        step_tag = f"-H{self.trades_today}" if self.trades_today > 1 else ""

        if direction == "BUY":
            return {
                "type": "BUY", "agent": agent_tag, "conv": f"{conv_tag}{step_tag}", "risk_pct": risk_pct,
                "entry": entry_price, "entry_time": now_ts,
                "entry_str": dt.strftime("%Y-%m-%d %H:%M"), "entry_hour": dt.hour,
                "sl": entry_price - sl_dist, "tp": entry_price + tp_dist,
                "be_trigger": entry_price + (sl_dist * 0.95),
                "sl_dist": sl_dist,
                "oz": oz, "comm": comm, "atr": atr_val, "is_be": False, "max_fav_r": 0.0
            }
        else:
            return {
                "type": "SELL", "agent": agent_tag, "conv": f"{conv_tag}{step_tag}", "risk_pct": risk_pct,
                "entry": entry_price, "entry_time": now_ts,
                "entry_str": dt.strftime("%Y-%m-%d %H:%M"), "entry_hour": dt.hour,
                "sl": entry_price + sl_dist, "tp": entry_price - tp_dist,
                "be_trigger": entry_price - (sl_dist * 0.95),
                "sl_dist": sl_dist,
                "oz": oz, "comm": comm, "atr": atr_val, "is_be": False, "max_fav_r": 0.0
            }

    def record_close(self, net_pnl, exit_reason):
        self.equity += net_pnl

        if ("Rollover" in exit_reason or "Weekend-Close" in exit_reason) and self.trades_today == 0:
            if net_pnl < -20.0:
                self.consecutive_losses += 1
            elif net_pnl > 20.0:
                self.consecutive_losses = 0
            return

        if "BE+" in exit_reason:
            self.today_be_locked = True
            return

        if "-TP" in exit_reason and net_pnl > 0:
            self.tp_wins_today += 1
            self.consecutive_losses = 0
        else:
            self.today_loss_locked = True
            if net_pnl < -20.0:
                self.consecutive_losses += 1
