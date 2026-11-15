def evaluate_advisor_recovery_signal(bar, prev, atr_val=0.0):
    """
    SL-Recovery Advisor Engine (V19):
    - ทำงานทันทีเมื่อระบบหลักโดน Stop Loss ในวันนั้น (today_loss_locked = True)
    - ใช้ตรรกะ Trend Impulse & Macro Order Flow ขี่เทรนด์ตามความรุนแรงของแท่งเทียน ห้ามสวนเด็ดขาด
    """
    if atr_val <= 0:
        return None, ""

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    chop_v = float(bar.get("chop", 50.0))
    
    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])
    
    has_oi = bool(bar.get("macro_bull_conv", False)) or bool(bar.get("macro_bear_conv", False))
    body_size = abs(close_p - open_p)

    # Advisor กู้พอร์ตเฉพาะตอนตลาดมีเทรนด์ชัดเจน (CHOP < 44.0), มี Macro OI หนุน, และแท่งเทียนกระชากแรง >= 0.8 ATR
    if chop_v < 44.0 and has_oi and body_size >= (atr_val * 0.80):
        if close_p > open_p and h1_bull and h4_bull:
            return "BUY", "ADVISOR-RECOVERY"
        if close_p < open_p and h1_bear and h4_bear:
            return "SELL", "ADVISOR-RECOVERY"

    return None, ""
