def evaluate_advisor_recovery_signal(bar, prev, atr_val=0.0):
    """
    SL-Recovery & Squeeze Breakout Advisor Engine (V20):
    - ทำหน้าที่ทันทีเมื่อระบบหลักโดน Stop Loss (today_loss_locked = True)
    - ใช้ตรรกะ Volatility Squeeze Expansion + Kaufman Efficiency Ratio (ER >= 0.35) + H1/H4 Trend
    - ห้ามดักสวนเด็ดขาด ให้รอจังหวะราคากระชากทะลุกรอบแล้วไหลตามน้ำ
    """
    if atr_val <= 0:
        return None, ""

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    er_val = float(bar.get("er", 0.30))
    atr_ratio = float(bar.get("atr_ratio", 1.0))
    
    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"] < float(bar["h1_ema"]))
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"] < float(bar["h4_ema"]))
    
    utc_hour = int(bar["thai_hour"]) - 7
    if utc_hour < 0:
        utc_hour += 24
    utc_mins = utc_hour * 60 + int(bar["thai_minute"])

    # ทำงานเฉพาะช่วงตลาดลอนดอนบ่ายถึงนิวยอร์ก (13:30 - 17:30 UTC / 20:30 - 00:30 น. ไทย)
    if not ((13 * 60 + 30) <= utc_mins <= (17 * 60 + 30)):
        return None, ""

    # ตรรกะกู้ชีพ: ตลาดเพิ่งระเบิดตัวจาก Squeeze (atr_ratio ขยายตัว > 1.0) และมีทิศทางชัดเจนตาม ER
    if er_val >= 0.35 and atr_ratio >= 1.0:
        if close_p > vwap_p and close_p > open_p and h1_bull and h4_bull:
            return "BUY", "ADVISOR-RECOVERY"
        if close_p < vwap_p and close_p < open_p and h1_bear and h4_bear:
            return "SELL", "ADVISOR-RECOVERY"

    return None, ""
