def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนตัดสินใจ V3:
    - ใช้ H4 + H1 Alignment (ต้องสอดคล้องกันทั้ง 2 Timeframe ถึงจะเปิดฝั่งนั้น ป้องกันการสวนเทรนด์ใหญ่)
    - Agent 1 (VWAP-PB): เข้าจังหวะย่อตัวแตะ Session VWAP แล้วไปต่อตามเทรนด์ H1/H4
    - Agent 2 (SWEEP): กวาดสภาพคล่องสุดขอบ VWAP Band + Swing 16 แท่งแล้วดึงกลับ
    - Agent 3 (NY-PULSE): จับแรงส่งช่วงเปิดตลาดสหรัฐฯ (19:30 - 21:45 น.) เพื่อให้ออกไม้ครบทุกวันทำการ
    """
    t_mins = int(bar["thai_mins"])
    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    vwrsi_v = float(bar["vwrsi"])

    if not ((9 * 60) <= t_mins <= (22 * 60)):
        return None, ""

    # เทรนด์ใหญ่ H4 และเทรนด์รอง H1 ต้องไปทางเดียวกัน (Dual-TF Alignment)
    macro_bull = (float(bar["h4_close"]) >= float(bar["h4_ema"])) and (float(bar["h1_close"]) >= float(bar["h1_ema"]))
    macro_bear = (float(bar["h4_close"]) < float(bar["h4_ema"])) and (float(bar["h1_close"]) < float(bar["h1_ema"]))

    # --- Agent 1: Institutional Liquidity Sweep (ต้องทะลุขอบ VWAP Band + Swing 16 แท่ง) ---
    bull_sweep = (bar["low"] < bar["swing_low"]) and (bar["low"] <= bar["vwap_lower"]) and (close_p > bar["swing_low"]) and (close_p > open_p)
    bear_sweep = (bar["high"] > bar["swing_high"]) and (bar["high"] >= bar["vwap_upper"]) and (close_p < bar["swing_high"]) and (close_p < open_p)

    if macro_bull and bull_sweep and (vwrsi_v < 45) and (vwrsi_v > prev["vwrsi"]):
        return "LONG", "SWEEP"
    if macro_bear and bear_sweep and (vwrsi_v > 55) and (vwrsi_v < prev["vwrsi"]):
        return "SHORT", "SWEEP"

    # --- Agent 2: Session VWAP Pullback (เกิดบ่อยตลอดวันตั้งแต่ 11:00 น. เป็นต้นไป) ---
    if t_mins >= (11 * 60):
        if macro_bull and (prev["low"] <= prev["vwap"]) and (close_p > vwap_p) and (close_p > open_p) and (51 <= vwrsi_v <= 70):
            return "LONG", "VWAP-PB"
        if macro_bear and (prev["high"] >= prev["vwap"]) and (close_p < vwap_p) and (close_p < open_p) and (30 <= vwrsi_v <= 49):
            return "SHORT", "VWAP-PB"

    # --- Agent 3: NY Opening Momentum Pulse (19:30 - 21:45 น. รับประกันการออกไม้ประจำวัน) ---
    if (19 * 60 + 30) <= t_mins <= (21 * 60 + 45):
        if macro_bull and (close_p > vwap_p) and (vwrsi_v > 52) and (close_p > open_p):
            return "LONG", "NY-PULSE"
        if macro_bear and (close_p < vwap_p) and (vwrsi_v < 48) and (close_p < open_p):
            return "SHORT", "NY-PULSE"

    return None, ""
