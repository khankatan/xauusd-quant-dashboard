from engine.config import (
    INITIAL_CAPITAL, BASE_RISK_PCT, CONVICTION_RISK_PCT, THROTTLED_RISK_PCT,
    DAILY_TARGET_PCT, HARD_DAILY_DD_PCT, MAX_TRADES_PER_DAY, STOP_ON_BE_PLUS,
    SL_ATR_MULT, TP_ATR_MULT, BE_TRIGGER_R, COMMISSION_PER_OZ
)

class RiskGuard:
    def __init__(self, initial_capital=INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.equity = initial_capital
        self.lowest_equity = initial_capital

        # Max Overall DD คำนวณจากฐานเงินต้น $100,000 ตามกฎ FTMO (ห้ามเกิน 10% หรือต่ำกว่า $90,000)
        self.max_overall_dd_pct = 0.0
        self.max_overall_dd_cash = 0.0

        # Max Daily DD คำนวณจากยอดขาดทุนสูงสุดต่อวัน (ห้ามเกิน 3% ต่อวัน)
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
        self.consecutive_losses = 0

    def on_new_bar(self, bar_date):
        if self.current_day != bar_date:
            self.current_day = bar_date
            self.daily_start_eq = self.equity
            self.today_target_logged = False
            self.today_loss_locked = False
            self.today_be_locked = False
            self.trades_today = 0

        # 1. ตรวจสอบ Overall Drawdown จากฐานเงินต้น $100,000
        self.lowest_equity = min(self.lowest_equity, self.equity)
        dd_from_initial_cash = max(0.0, self.initial_capital - self.equity)
        dd_from_initial_pct = (dd_from_initial_cash / self.initial_capital) * 100.0
        if dd_from_initial_pct > self.max_overall_dd_pct:
            self.max_overall_dd_pct = dd_from_initial_pct
            self.max_overall_dd_cash = dd_from_initial_cash

        # 2. ตรวจสอบ Daily Drawdown ภายในวันปัจจุบัน
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
        if self.today_target_logged or self.today_loss_locked or self.today_be_locked:
            return False
        return self.trades_today < MAX_TRADES_PER_DAY

    def get_active_risk_pct(self, is_macro_conv=False):
        if self.consecutive_losses >= 2:
            return THROTTLED_RISK_PCT
        return CONVICTION_RISK_PCT if is_macro_conv else BASE_RISK_PCT

    def build_order(self, direction, agent_tag, entry_price, atr_val, dt, now_ts, is_macro_conv=False):
        sl_dist = atr_val * SL_ATR_MULT
        tp_dist = atr_val * TP_ATR_MULT
        if sl_dist <= 0:
            return None

        risk_pct = self.get_active_risk_pct(is_macro_conv)
        risk_cash = self.equity * (risk_pct / 100.0)
        oz = risk_cash / sl_dist
        comm = oz * COMMISSION_PER_OZ * 2
        self.trades_today += 1
        conv_tag = "+OI" if is_macro_conv else ""

        if direction == "LONG":
            return {
                "type": "LONG", "agent": agent_tag, "conv": conv_tag, "risk_pct": risk_pct,
                "entry": entry_price, "entry_time": now_ts,
                "entry_str": dt.strftime("%Y-%m-%d %H:%M"), "entry_hour": dt.hour,
                "sl": entry_price - sl_dist, "tp": entry_price + tp_dist,
                "be_trigger": entry_price + (sl_dist * BE_TRIGGER_R),
                "oz": oz, "comm": comm, "atr": atr_val, "is_be": False
            }
        else:
            return {
                "type": "SHORT", "agent": agent_tag, "conv": conv_tag, "risk_pct": risk_pct,
                "entry": entry_price, "entry_time": now_ts,
                "entry_str": dt.strftime("%Y-%m-%d %H:%M"), "entry_hour": dt.hour,
                "sl": entry_price + sl_dist, "tp": entry_price - tp_dist,
                "be_trigger": entry_price - (sl_dist * BE_TRIGGER_R),
                "oz": oz, "comm": comm, "atr": atr_val, "is_be": False
            }

    def record_close(self, net_pnl, exit_reason):
        self.equity += net_pnl
        if STOP_ON_BE_PLUS and "BE+" in exit_reason:
            self.today_be_locked = True
        if net_pnl < -20.0:
            self.consecutive_losses += 1
        elif net_pnl > 20.0:
            self.consecutive_losses = 0
