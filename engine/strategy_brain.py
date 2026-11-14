def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนตัดสินใจ V6 (คัดเฉพาะ Logic ที่ทำกำไรจริงจากผล Audit V3-V5):
    1. Agent VWAP-PB (Exact Touch): คืนเงื่อนไขต้องแตะเส้น Session VWAP จริง (ทำกำไร +$495 ถึง +$746)
       พร้อมกรอง H4 Trend Alignment เพื่อตัดไม้สวนเทรนด์ใหญ่
    2. Agent EV-PB (Evening Pullback): ทำงานช่วง 18:15 - 21:30 น. (ทำกำไร +$50.61 ใน V5)
       เก็บจังหวะย่อพักตัวช่วงตลาดสหรัฐฯ เพื่อให้ออกไม้ครบทุกวันทำการ
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

    # --- Agent 1: Exact Session VWAP Pullback (เงื่อนไขพิสูจน์แล้วจาก V3/V4) ---
    # ต้องแตะ/ทะลุเส้น VWAP จริงในแท่งก่อนหน้า แล้วปิดแท่งกลับตัวตามเทรนด์ H1
    if h1_bull and (prev["low"] <= prev["vwap"]) and (close_p > vwap_p) and (close_p > open_p):
        # หาก H4 เห็นพ้องด้วย ใช้เกณฑ์ปกติ (50-70) / หาก H4 สวนทาง ต้องรอแรงส่งชัด (54-68)
        min_rsi = 50 if h4_bull else 54
        if (min_rsi <= vwrsi_v <= 70) and (vwrsi_v > prev["vwrsi"]):
            return "LONG", "VWAP-PB"

    if h1_bear and (prev["high"] >= prev["vwap"]) and (close_p < vwap_p) and (close_p < open_p):
        max_rsi = 50 if h4_bear else 46
        if (30 <= vwrsi_v <= max_rsi) and (vwrsi_v < prev["vwrsi"]):
            return "SHORT", "VWAP-PB"

    # --- Agent 2: Evening Pullback to Value (18:15 - 21:30 น. เพื่อให้ออกไม้ครบทุกวันทำการ) ---
    if (18 * 60 + 15) <= t_mins <= (21 * 60 + 30):
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])
        if h1_bull and h4_bull and prev_red and (close_p > open_p) and (close_p > vwap_p) and (52 <= vwrsi_v <= 68):
            return "LONG", "EV-PB"
        if h1_bear and h4_bear and prev_green and (close_p < open_p) and (close_p < vwap_p) and (32 <= vwrsi_v <= 48):
            return "SHORT", "EV-PB"

    return None, ""
