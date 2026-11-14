from engine.config import (
    BASE_RISK_PCT, THROTTLED_RISK_PCT, DAILY_TARGET_PCT,
    HARD_DAILY_DD_PCT, MAX_TRADES_PER_DAY, STOP_ON_BE_PLUS,
    SL_ATR_MULT, TP_ATR_MULT, BE_TRIGGER_R, COMMISSION_PER_OZ
)

class RiskGuard:
    def __init__(self, initial_capital):
        self.equity = initial_capital
        self.peak_equity = initial_capital
        self.max_dd_pct = 0.0
        self.max_daily_dd_pct = 0.0

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

        self.peak_equity = max(self.peak_equity, self.equity)
        self.max_dd_pct = max(self.max_dd_pct, ((self.peak_equity - self.equity) / self.peak_equity) * 100.0)

        daily_pnl_pct = ((self.equity - self.daily_start_eq) / self.daily_start_eq) * 100.0
        if daily_pnl_pct < 0:
            self.max_daily_dd_pct = max(self.max_daily_dd_pct, abs(daily_pnl_pct))

        if daily_pnl_pct >= DAILY_TARGET_PCT and not self.today_target_logged:
            self.days_hit_target += 1
            self.today_target_logged = True

        if daily_pnl_pct <= -HARD_DAILY_DD_PCT:
            self.today_loss_locked = True

    def can_trade(self):
        if self.today_target_logged or self.today_loss_locked or self.today_be_locked:
            return False
        return self.trades_today < MAX_TRADES_PER_DAY

    def get_active_risk_pct(self):
        return THROTTLED_RISK_PCT if self.consecutive_losses >= 2 else BASE_RISK_PCT

    def build_order(self, direction, agent_tag, entry_price, atr_val, dt, now_ts):
        sl_dist = atr_val * SL_ATR_MULT
        tp_dist = atr_val * TP_ATR_MULT
        if sl_dist <= 0:
            return None

        risk_cash = self.equity * (self.get_active_risk_pct() / 100.0)
        oz = risk_cash / sl_dist
        comm = oz * COMMISSION_PER_OZ * 2
        self.trades_today += 1

        if direction == "LONG":
            return {
                "type": "LONG", "agent": agent_tag, "entry": entry_price, "entry_time": now_ts,
                "entry_str": dt.strftime("%Y-%m-%d %H:%M"), "entry_hour": dt.hour,
                "sl": entry_price - sl_dist, "tp": entry_price + tp_dist,
                "be_trigger": entry_price + (sl_dist * BE_TRIGGER_R),
                "oz": oz, "comm": comm, "atr": atr_val, "is_be": False
            }
        else:
            return {
                "type": "SHORT", "agent": agent_tag, "entry": entry_price, "entry_time": now_ts,
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
