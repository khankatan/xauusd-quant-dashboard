from engine.config import (
    INITIAL_CAPITAL, BASE_RISK_PCT, CONVICTION_RISK_PCT, THROTTLED_RISK_PCT,
    DAILY_TARGET_PCT, HARD_DAILY_DD_PCT, MAX_TRADES_PER_DAY, STOP_ON_BE_PLUS,
    HOUSE_MONEY_MODE, SL_ATR_MULT, TP_ATR_MULT, BE_TRIGGER_R, PARTIAL_TP_RATIO,
    COMMISSION_PER_OZ
)

def get_agent_sl_tp_mult(agent_tag):
    """ปรับระยะ SL / TP2 ตามรสชาติของตลาด"""
    if "SALTY" in agent_tag:
        return 1.8, 2.3   # รสเค็ม (ไซด์เวย์): SL 1.8 / TP2 2.3 ATR
    if "SOUR" in agent_tag:
        return 2.0, 2.8   # รสเปรี้ยว (กับดักกวาด SL): SL 2.0 / TP2 2.8 ATR
    return SL_ATR_MULT, TP_ATR_MULT  # รสหวาน (เทรนด์): SL 2.0 / TP2 3.0 ATR

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

    def build_order(self, direction, agent_tag, entry_price, atr_val, dt, now_ts, is_macro_conv=False, **kwargs):
        sl_mult, tp_mult = get_agent_sl_tp_mult(agent_tag)
        sl_dist = atr_val * sl_mult
        tp_dist = atr_val * tp_mult
        if sl_dist <= 0:
            return None

        risk_pct = self.get_active_risk_pct(is_macro_conv)
        risk_cash = self.equity * (risk_pct / 100.0)
        oz = risk_cash / sl_dist
        comm = oz * COMMISSION_PER_OZ * 2
        self.trades_today += 1

        conv_tag = "+OI" if is_macro_conv else ""
        step_tag = f"-H{self.trades_today}" if self.trades_today > 1 else ""

        # คำนวณจุด TP1 (ระยะ 1.15 R สำหรับแบ่งปิดกำไร 50% แรก และยก SL บังหน้าทุนที่ 0.08 ATR เดิม)
        tp1_dist = min(sl_dist * BE_TRIGGER_R, tp_dist * 0.85)

        if direction == "BUY":
            return {
                "type": "BUY", "agent": agent_tag, "conv": f"{conv_tag}{step_tag}", "risk_pct": risk_pct,
                "entry": entry_price, "entry_time": now_ts,
                "entry_str": dt.strftime("%Y-%m-%d %H:%M"), "entry_hour": dt.hour,
                "sl": entry_price - sl_dist,
                "tp1": entry_price + tp1_dist,
                "tp": entry_price + tp_dist,
                "be_trigger": entry_price + tp1_dist,
                "sl_dist": sl_dist,
                "oz": oz, "rem_oz": oz, "comm": comm, "atr": atr_val,
                "is_be": False, "partial_closed": False, "partial_pnl": 0.0,
                "partial_ratio": PARTIAL_TP_RATIO, "max_fav_r": 0.0
            }
        else:
            return {
                "type": "SELL", "agent": agent_tag, "conv": f"{conv_tag}{step_tag}", "risk_pct": risk_pct,
                "entry": entry_price, "entry_time": now_ts,
                "entry_str": dt.strftime("%Y-%m-%d %H:%M"), "entry_hour": dt.hour,
                "sl": entry_price + sl_dist,
                "tp1": entry_price - tp1_dist,
                "tp": entry_price - tp_dist,
                "be_trigger": entry_price - tp1_dist,
                "sl_dist": sl_dist,
                "oz": oz, "rem_oz": oz, "comm": comm, "atr": atr_val,
                "is_be": False, "partial_closed": False, "partial_pnl": 0.0,
                "partial_ratio": PARTIAL_TP_RATIO, "max_fav_r": 0.0
            }

    def record_close(self, net_pnl, exit_reason):
        self.equity += net_pnl

        if ("Rollover" in exit_reason or "Weekend-Close" in exit_reason) and self.trades_today == 0:
            if net_pnl < -20.0:
                self.consecutive_losses += 1
            elif net_pnl > 20.0:
                self.consecutive_losses = 0
            return

        # กรณีชน BE+ (ทั้งแบบแบ่งปิดกำไร TP1+BE+ หรือ Late-Night BE+): ล็อกกำไรวันนี้และรีเซ็ตสถิติแพ้ติดกัน
        if "BE+" in exit_reason:
            self.today_be_locked = True
            if net_pnl > 20.0:
                self.consecutive_losses = 0
            return

        # กรณีชนะชนเป้าใหญ่ TP2 (-TP1+TP2 หรือ -TP): เปิดโควตา House Money ให้มองหาไม้ถัดไปได้
        if ("TP2" in exit_reason or exit_reason.endswith("-TP")) and net_pnl > 0:
            self.tp_wins_today += 1
            self.consecutive_losses = 0
        else:
            self.today_loss_locked = True
            if net_pnl < -20.0:
                self.consecutive_losses += 1
