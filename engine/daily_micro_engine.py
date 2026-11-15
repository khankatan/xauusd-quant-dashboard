def evaluate_daily_micro_engine(bar, prev, trades_today=0):
    """
    เอนจิ้นตัวที่ 3 (Micro-Scalp Closer & Daily Minimum 1-Trade Guarantee):
    - ไม่เพิ่มความเสี่ยงพอร์ต (ใช้ Micro-Risk 0.15% ต่อไม้)
    - 1) ช่วง 14:30 - 16:30 UTC (21:30 - 23:30 TH): เก็บกำไรไซด์เวย์เข้าหา VWAP เมื่อ CHOP >= 50.0
    - 2) ช่วง 17:15 - 17:45 UTC (00:15 - 00:45 TH): หากทั้งวันยังไม่ออกไม้เลย ให้เปิดไม้ตามแรงแท่งเทียนเพื่อการันตีขั้นต่ำ 1 ไม้/วัน
    """
    if trades_today > 0:
        return None, ""

    utc_hour = int(bar["thai_hour"]) - 7
    if utc_hour < 0:
        utc_hour += 24
    utc_mins = utc_hour * 60 + int(bar["thai_minute"])

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    chop_v = float(bar.get("chop", 50.0))
    prev_z = float(prev.get("fast_z", 0.0))
    vwrsi_v = float(bar["vwrsi"])
    prev_rsi = float(prev["vwrsi"])

    # 1. Sideways Micro-Scalp (21:30 - 23:30 TH): ดันกำไรเดือนไซด์เวย์ (เม.ย. / ก.ค.)
    if (14 * 60 + 30) <= utc_mins <= (16 * 60 + 30) and chop_v >= 50.0:
        if prev_z <= -1.45 and close_p > open_p and vwrsi_v > prev_rsi and close_p < vwap_p:
            return "BUY", "MICRO-RANGE"
        if prev_z >= 1.45 and close_p < open_p and vwrsi_v < prev_rsi and close_p > vwap_p:
            return "SELL", "MICRO-RANGE"

    # 2. Daily Minimum 1-Trade Guarantee (00:15 - 00:45 TH): ปิดช่องว่าง 33 วันที่เหลือให้ครบ 1 ไม้/วัน
    if (17 * 60 + 15) <= utc_mins <= (17 * 60 + 45):
        if close_p > open_p:
            return "BUY", "MICRO-DAILY"
        if close_p < open_p:
            return "SELL", "MICRO-DAILY"

    return None, ""
