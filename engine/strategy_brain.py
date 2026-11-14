def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนตัดสินใจ V7.3:
    1. Agent VWAP-PB: ย่อทดสอบเส้น Session VWAP จริง แล้วไปต่อตามเทรนด์ H1 (+กรอง H4)
    2. Agent EV-PB: จับแรงส่งช่วงค่ำ (18:15 - 21:30 น.) รองรับทั้ง H4 Alignment และ OI+DXY Conviction
    """
    t_mins = int(bar["thai_mins"])
    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    vwrsi_v = float(bar["vwrsi"])

    # เทรดเฉพาะช่วง 09:30 - 21:45 น. เวลาไทย (ลดโอกาสโดน Rollover ค้างคืน)
    if not ((9 * 60 + 30) <= t_mins <= (21 * 60 + 45)):
        return None, ""

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    macro_bull_conv = bool(bar.get("macro_bull_conv", False))
    macro_bear_conv = bool(bar.get("macro_bear_conv", False))

    # --- Agent 1: Exact Session VWAP Pullback ---
    if h1_bull and (prev["low"] <= prev["vwap"]) and (close_p > vwap_p) and (close_p > open_p):
        min_rsi = 50 if (h4_bull or macro_bull_conv) else 54
        if (min_rsi <= vwrsi_v <= 70) and (vwrsi_v > prev["vwrsi"]):
            return "BUY", "VWAP-PB"

    if h1_bear and (prev["high"] >= prev["vwap"]) and (close_p < vwap_p) and (close_p < open_p):
        max_rsi = 50 if (h4_bear or macro_bear_conv) else 46
        if (30 <= vwrsi_v <= max_rsi) and (vwrsi_v < prev["vwrsi"]):
            return "SELL", "VWAP-PB"

    # --- Agent 2: Evening Pullback to Value (18:15 - 21:30 น.) ---
    # อนุญาตให้เข้าเมื่อ (H1 + H4 ตรงกัน) หรือ (H1 ตรงกับวันที่มี OI+DXY Conviction ยืนยันเทรนด์จริง)
    if (18 * 60 + 15) <= t_mins <= (21 * 60 + 30):
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])

        if h1_bull and (h4_bull or macro_bull_conv) and prev_red and (close_p > open_p) and (close_p > vwap_p) and (52 <= vwrsi_v <= 68):
            return "BUY", "EV-PB"

        if h1_bear and (h4_bear or macro_bear_conv) and prev_green and (close_p < open_p) and (close_p < vwap_p) and (32 <= vwrsi_v <= 48):
            return "SELL", "EV-PB"

    return None, ""
