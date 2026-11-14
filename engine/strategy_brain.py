def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนตัดสินใจ: รวม 3 เอเจนต์เฉพาะทางเพื่อให้เกิดสัญญาณคุณภาพได้ทุกวันทำการ
    1. Agent Sweep: จับจังหวะ Liquidity Sweep + VWRSI Reversal (ได้ทั้งรอบเช้า-บ่าย-ค่ำ)
    2. Agent Session: จับจังหวะเบรกกรอบเอเชีย (Asian Breakout) ตามทิศทาง Session VWAP
    3. Agent NY-Pulse: จับจังหวะเปิดตลาดนิวยอร์ก (19:30-21:30 น.) หากทั้งวันยังไม่เกิดไม้
    """
    t_mins = int(bar["thai_mins"])
    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    vwrsi_v = float(bar["vwrsi"])
    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])

    # จำกัดเวลาหาสัญญาณ 08:30 - 22:30 น. เวลาไทย (ป้องกันออเดอร์ค้างข้ามคืนโดน Rollover)
    if not ((8 * 60 + 30) <= t_mins <= (22 * 60 + 30)):
        return None, ""

    # --- Agent 1: Institutional Liquidity Sweep + VWAP Band ---
    bull_sweep = (bar["low"] < bar["swing_low"]) and (close_p > bar["swing_low"]) and (close_p > open_p)
    bear_sweep = (bar["high"] > bar["swing_high"]) and (close_p < bar["swing_high"]) and (close_p < open_p)

    if h1_bull and bull_sweep and (bar["low"] <= bar["vwap_lower"]) and (vwrsi_v < 46) and (vwrsi_v > prev["vwrsi"]):
        return "LONG", "SWEEP"
    if (not h1_bull) and bear_sweep and (bar["high"] >= bar["vwap_upper"]) and (vwrsi_v > 54) and (vwrsi_v < prev["vwrsi"]):
        return "SHORT", "SWEEP"

    # --- Agent 2: London-NY Session Breakout (หลัง 14:00 น. เวลาไทย) ---
    if t_mins >= (14 * 60) and asian_bars >= 4:
        if h1_bull and (close_p > asian_high) and (close_p > vwap_p) and (vwrsi_v > 53) and (close_p > open_p):
            return "LONG", "ASIA-BRK"
        if (not h1_bull) and (close_p < asian_low) and (close_p < vwap_p) and (vwrsi_v < 47) and (close_p < open_p):
            return "SHORT", "ASIA-BRK"

    # --- Agent 3: NY Opening Momentum Fallback (19:30 - 21:30 น. เพื่อให้ออกไม้ครบทุกวันทำการ) ---
    if (19 * 60 + 30) <= t_mins <= (21 * 60 + 30):
        if h1_bull and (close_p > vwap_p) and (vwrsi_v > 54) and (close_p > open_p):
            return "LONG", "NY-MOM"
        if (not h1_bull) and (close_p < vwap_p) and (vwrsi_v < 46) and (close_p < open_p):
            return "SHORT", "NY-MOM"

    return None, ""
