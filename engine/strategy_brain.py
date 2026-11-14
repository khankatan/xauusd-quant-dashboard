def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนตัดสินใจ V5 (ปรับจูนจากผล Audit all_trades 15):
    - ตัดสมอง NY-PULSE ที่ไล่ราคาตอนเปิดลอนดอน (-$1,496.47) ทิ้งถาวร
    - ใช้หลักการ Mean-Reversion Pullback to Value 100% (ห้ามไล่ราคาเมื่อราคาวิ่งห่างเส้นค่าเฉลี่ย):
      1. Agent VWAP-ZONE: ราคาย่อตัวเข้าใกล้เส้น Session VWAP (ในระยะ 0.35 ATR) แล้วดีดกลับตามเทรนด์ H1
      2. Agent EMA20-PB (หลัง 18:00 น.): หากทั้งวันราคายังวิ่งแรงไม่ย่อถึง VWAP ให้เข้าเมื่อราคาย่อทดสอบ M15 EMA20 (Fast Value Zone) เพื่อให้ออกไม้ครบทุกวันทำการอย่างปลอดภัย
    """
    t_mins = int(bar["thai_mins"])
    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    atr_v = float(bar["atr"])
    vwrsi_v = float(bar["vwrsi"])

    # เทรดเฉพาะช่วง 09:30 - 22:00 น. เวลาไทย (ป้องกันออเดอร์ค้างข้ามคืนโดน Rollover)
    if not ((9 * 60 + 30) <= t_mins <= (22 * 60)):
        return None, ""

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])

    # โซนมูลค่าของสถาบันรอบเส้น VWAP (±0.35 ATR)
    vwap_buffer = atr_v * 0.35

    # --- Agent 1: Session VWAP Value-Zone Pullback (พระเอก PF 1.17 - 2.23) ---
    # ขาขึ้น H1: ราคาย่อลงมาแตะโซน VWAP (ต่ำกว่า vwap + 0.35 ATR) และไม่หลุดลึกเกินไป แล้วปิดแท่งเขียวยกตัว
    near_vwap_long = (prev["low"] <= (vwap_p + vwap_buffer)) and (close_p >= (vwap_p - vwap_buffer))
    if h1_bull and near_vwap_long and (close_p > open_p) and (48 <= vwrsi_v <= 68) and (vwrsi_v > prev["vwrsi"]):
        return "LONG", "VWAP-PB"

    # ขาลง H1: ราคาเด้งขึ้นมาแตะโซน VWAP (สูงกว่า vwap - 0.35 ATR) แล้วถูกตบปิดแท่งแดงหักลง
    near_vwap_short = (prev["high"] >= (vwap_p - vwap_buffer)) and (close_p <= (vwap_p + vwap_buffer))
    if h1_bear and near_vwap_short and (close_p < open_p) and (32 <= vwrsi_v <= 52) and (vwrsi_v < prev["vwrsi"]):
        return "SHORT", "VWAP-PB"

    # --- Agent 2: Evening Pullback to Fast Value (หลัง 18:00 น. หากทั้งวันยังไม่ได้ไม้) ---
    # เข้าเฉพาะเมื่อราคา "ย่อพักตัว" (แท่งก่อนหน้าสวนเทรนด์) แล้วแท่งปัจจุบันกลับตัวตามเทรนด์ H1 (ไม่ไล่ราคา)
    if t_mins >= (18 * 60):
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])
        if h1_bull and prev_red and (close_p > open_p) and (close_p > vwap_p) and (50 <= vwrsi_v <= 70):
            return "LONG", "EV-PB"
        if h1_bear and prev_green and (close_p < open_p) and (close_p < vwap_p) and (30 <= vwrsi_v <= 50):
            return "SHORT", "EV-PB"

    return None, ""
