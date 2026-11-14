def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนตัดสินใจ V4 (ปรับจูนจากผล Audit all_trades 14):
    - ตัดสมอง SWEEP ที่ขาดทุน (-$767.38, WR 20%) ออกถาวร
    - โฟกัสเฉพาะ 2 สมองที่ทำกำไรจริง:
      1. Agent VWAP-PB (PF 2.23, WR 66.67%): ราคาย่อทดสอบ Session VWAP แล้วไปต่อตามเทรนด์ H1
      2. Agent NY-PULSE (PF 1.25): จับแรงส่งช่วงตลาดลอนดอน-นิวยอร์ก (16:00 - 21:45 น.) เพื่อให้ออกไม้ครบทุกวันทำการ
    """
    t_mins = int(bar["thai_mins"])
    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    vwrsi_v = float(bar["vwrsi"])

    # เทรดเฉพาะช่วง 09:00 - 22:00 น. เวลาไทย (ป้องกันออเดอร์ค้างข้ามคืนโดน Rollover)
    if not ((9 * 60) <= t_mins <= (22 * 60)):
        return None, ""

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])

    # --- Agent 1: Session VWAP Pullback (พระเอก PF 2.23 — เปิดให้ทำงานตั้งแต่ 09:30 น. เพื่อจับรอบเช้าและบ่าย) ---
    if t_mins >= (9 * 60 + 30):
        # ขาขึ้น H1: ราคาย่อลงมาแตะ/ใต้เส้น VWAP แล้วดีดปิดแท่งเขียวยืนเหนือ VWAP พร้อม VWRSI ยกตัว
        if h1_bull and (prev["low"] <= prev["vwap"]) and (close_p > vwap_p) and (close_p > open_p) and (50 <= vwrsi_v <= 72) and (vwrsi_v >= prev["vwrsi"]):
            return "LONG", "VWAP-PB"
        # ขาลง H1: ราคาเด้งขึ้นไปแตะ/เหนือเส้น VWAP แล้วถูกตบปิดแท่งแดงใต้ VWAP พร้อม VWRSI หักลง
        if h1_bear and (prev["high"] >= prev["vwap"]) and (close_p < vwap_p) and (close_p < open_p) and (28 <= vwrsi_v <= 50) and (vwrsi_v <= prev["vwrsi"]):
            return "SHORT", "VWAP-PB"

    # --- Agent 2: London-NY Momentum Pulse (16:30 - 21:45 น. เพื่อให้ออกไม้ครบทุกวันทำการ) ---
    if (16 * 60 + 30) <= t_mins <= (21 * 60 + 45):
        if h1_bull and (close_p > vwap_p) and (vwrsi_v > 52) and (close_p > open_p):
            return "LONG", "NY-PULSE"
        if h1_bear and (close_p < vwap_p) and (vwrsi_v < 48) and (close_p < open_p):
            return "SHORT", "NY-PULSE"

    return None, ""
