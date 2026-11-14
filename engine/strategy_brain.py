def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนตัดสินใจ V8 (Dynamic Regime-Adaptive):
    1. Dynamic Volatility Shock Guard: งดเข้าเฉพาะแท่งที่ ATR พุ่งเกิน 1.85 เท่าของฐาน 100 แท่งล่าสุด (ปรับตามราคาและฤดูกาลอัตโนมัติ)
    2. Prime Liquidity Windows: เทรดช่วง 11:00-14:45 น. และ 17:30-21:45 น. (เลี่ยงช่วงสะบัดเปิดเช้า 09:00-10:59 และเปิดลอนดอน 15:00-16:59)
    3. Strict Multi-Timeframe Trend Alignment: ทั้ง VWAP-PB และ EV-PB ต้องไปทางเดียวกับ H1 และ H4 เสมอ
    """
    t_mins = int(bar["thai_mins"])
    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    vwrsi_v = float(bar["vwrsi"])
    atr_ratio = float(bar.get("atr_ratio", 1.0))

    # 1. Dynamic Shock Guard: กันเฉพาะข่าวกระชากฉับพลันเกิน 1.85x ของฐานความผันผวนช่วงนั้น
    if atr_ratio > 1.85:
        return None, ""

    # 2. Prime Liquidity Windows
    in_midday_session = (11 * 60) <= t_mins <= (14 * 60 + 45)
    in_ny_session = (17 * 60 + 30) <= t_mins <= (21 * 60 + 45)
    if not (in_midday_session or in_ny_session):
        return None, ""

    # 3. Strict Multi-Timeframe Alignment (H1 + H4 ต้องสอดคล้องกัน 100%)
    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    # --- Agent 1: Exact Session VWAP Pullback ---
    if h1_bull and h4_bull and (prev["low"] <= prev["vwap"]) and (close_p > vwap_p) and (close_p > open_p):
        if (50 <= vwrsi_v <= 70) and (vwrsi_v > prev["vwrsi"]):
            return "BUY", "VWAP-PB"

    if h1_bear and h4_bear and (prev["high"] >= prev["vwap"]) and (close_p < vwap_p) and (close_p < open_p):
        if (30 <= vwrsi_v <= 50) and (vwrsi_v < prev["vwrsi"]):
            return "SELL", "VWAP-PB"

    # --- Agent 2: Evening Pullback to Value (18:15 - 21:45 น.) ---
    if (18 * 60 + 15) <= t_mins <= (21 * 60 + 45):
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])
        if h1_bull and h4_bull and prev_red and (close_p > open_p) and (close_p > vwap_p) and (52 <= vwrsi_v <= 68):
            return "BUY", "EV-PB"
        if h1_bear and h4_bear and prev_green and (close_p < open_p) and (close_p < vwap_p) and (32 <= vwrsi_v <= 48):
            return "SELL", "EV-PB"

    return None, ""
