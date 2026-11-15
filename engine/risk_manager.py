from engine.config import (
    INITIAL_CAPITAL, BASE_RISK_PCT, CONVICTION_RISK_PCT, THROTTLED_RISK_PCT,
    DAILY_TARGET_PCT, HARD_DAILY_DD_PCT, MAX_TRADES_PER_DAY,
    SL_ATR_MULT, TP_ATR_MULT, BE_TRIGGER_R, PARTIAL_TP_RATIO,
    COMMISSION_PER_OZ, HOUSE_MONEY_MODE, STEP_LOCK_TRIGGER_R, STEP_LOCK_LOCK_R
)

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
        self.first_trade_has_oi = False  # บันทึกสถานะ +OI ของไม้แรก

    def on_new_bar(self, bar_date):
        if self.current_day != bar_date:
            self.current_day = bar_date
            self.daily_start_eq = self.equity
            self.today_target_logged = False
            self.today_loss_locked = False
            self.today_be_locked = False
            self.trades_today = 0
            self.tp_wins_today = 0
            self.first_trade_has_oi = False

    def can_trade(self):
        if self.today_loss_locked or self.today_be_locked:
            return False
        if self.trades_today == 0:
            return True
        
        # --- กฎข้อ 2: H2 House Money +OI Guard ---
        # หากจะยิงไม้สอง (H2) ต้องมี +OI ยืนยันเสมอ และไม้แรกต้องมี +OI ด้วย หากไม่มีให้จบวันทันที
        if HOUSE_MONEY_MODE and self.trades_today == 1 and self.tp_wins_today == 1:
            if not self.first_trade_has_oi:
                return False  # ไม้แรกไม่มี OI ห้ามเปิดไม้สอง ล็อกกำไรจบวัน
            return True
        return False

    def record_close(self, net_pnl, exit_reason):
        self.equity += net_pnl
        if net_pnl > 0:
            self.tp_wins_today += 1
            self.consecutive_losses = 0
        else:
            self.today_loss_locked = True
            self.consecutive_losses += 1
