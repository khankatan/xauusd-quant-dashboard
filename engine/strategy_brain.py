def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนตัดสินใจ V2 (แก้จุดอ่อนจากผล Audit all_trades 12):
    - เลิกไล่ราคา Breakout กรอบเอเชียที่โดน False Breakout บ่อย
    - เปลี่ยนเป็น:
      1. Agent Sweep: จับจังหวะกวาด Swing High/Low (หรือกวาด Asian High/Low) แล้วดึงกลับตามเทรนด์ H1
      2. Agent VWAP-Pullback: จับจังหวะราคาย่อตัวมาทดสอบเส้น Session VWAP แล้วดีดกลับตามเทรนด์ H1 (ออกไม้ได้ทุกวัน)
    """
    t_mins = int(bar["thai_mins"])
    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    vwrsi_v = float(bar["vwrsi"])
    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])

    # เทรดเฉพาะช่วง 09:00 - 22:00 น. เวลาไทย (ป้องกันออเดอร์ค้างข้ามคืนโดน Rollover)
    if not ((9 * 60) <= t_mins <= (22 * 60)):
        return None, ""

    # --- Agent 1: Liquidity Sweep (กวาด Swing หรือกวาดกรอบ Asian High/Low แล้วดึงกลับ) ---
    sweep_low_level = min(float(bar["swing_low"]), asian_low) if asian_bars >= 4 else float(bar["swing_low"])
    sweep_high_level = max(float(bar["swing_high"]), asian_high) if asian_bars >= 4 else float(bar["swing_high"])

    bull_sweep = (bar["low"] < sweep_low_level) and (close_p > sweep_low_level) and (close_p > open_p)
    bear_sweep = (bar["high"] > sweep_high_level) and (close_p < sweep_high_level) and (close_p < open_p)

    if h1_bull and bull_sweep and (vwrsi_v < 48) and (vwrsi_v > prev["vwrsi"]):
        return "LONG", "SWEEP"
    if (not h1_bull) and bear_sweep and (vwrsi_v > 52) and (vwrsi_v < prev["vwrsi"]):
        return "SHORT", "SWEEP"

    # --- Agent 2: Session VWAP Pullback Continuation (เกิดได้ทุกวันทำการหลัง 13:30 น.) ---
    if t_mins >= (13 * 60 + 30):
        # ขาขึ้น H1: ราคาย่อลงมาแตะ/ใต้เส้น VWAP แล้วดีดปิดแท่งเขียวยืนเหนือ VWAP พร้อม VWRSI > 53
        if h1_bull and (prev["low"] <= prev["vwap"]) and (close_p > vwap_p) and (close_p > open_p) and (53 <= vwrsi_v <= 68) and (vwrsi_v > prev["vwrsi"]):
            return "LONG", "VWAP-PB"
        # ขาลง H1: ราคาเด้งขึ้นไปแตะ/เหนือเส้น VWAP แล้วถูกตบปิดแท่งแดงใต้ VWAP พร้อม VWRSI < 47
        if (not h1_bull) and (prev["high"] >= prev["vwap"]) and (close_p < vwap_p) and (close_p < open_p) and (32 <= vwrsi_v <= 47) and (vwrsi_v < prev["vwrsi"]):
            return "SHORT", "VWAP-PB"

    return None, ""
