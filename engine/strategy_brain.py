from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนกลาง V12.1:
    - SWEET: ย่อตัวหาเส้น KAMA/VWAP ในจังหวะ CHOP < 38.2 หรือต้นคลื่นเทรนด์ใหม่
    - SOUR: สวนกับดักกวาดสภาพคล่องเมื่อความเร่งพลิกกลับ
    - SALTY: ดักเด้งในกรอบ CHOP > 61.8 โดยห้ามสวนเทรนด์ใหญ่ H4 เด็ดขาด (แก้จุดรั่ว SALTY BUY -$2,206)
    """
    t_mins = int(bar["thai_mins"])
    if not ((9 * 60 + 30) <= t_mins <= (21 * 60 + 45)):
        return None, ""

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    kama_p = float(bar.get("kama", vwap_p))
    vwrsi_v = float(bar["vwrsi"])
    prev_rsi = float(prev["vwrsi"])
    fast_z = float(bar.get("fast_z", 0.0))
    accel_v = float(bar.get("accel", 0.0))
    p_accel = float(bar.get("price_accel", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars)

    if flavor == "BITTER":
        return None, ""

    # 1. โหมดรสหวาน (SWEET -> ย่อแตะเส้น KAMA หรือ VWAP แล้วเกิดความเร่งส่งตัวกลับตามเทรนด์)
    if flavor == "SWEET":
        pulled_to_bull_zone = (float(prev["low"]) <= float(prev["kama"])) or (float(prev["low"]) <= float(prev["vwap"]))
        pulled_to_bear_zone = (float(prev["high"]) >= float(prev["kama"])) or (float(prev["high"]) >= float(prev["vwap"]))

        if info["bull_trend"] and pulled_to_bull_zone and (close_p > open_p) and (close_p > kama_p):
            if (p_accel > 0.0) and (accel_v >= -0.01) and (50 <= vwrsi_v <= 66) and (fast_z < 1.05):
                return "BUY", "SWEET-TREND"

        if info["bear_trend"] and pulled_to_bear_zone and (close_p < open_p) and (close_p < kama_p):
            if (p_accel < 0.0) and (accel_v <= 0.01) and (34 <= vwrsi_v <= 50) and (fast_z > -1.05):
                return "SELL", "SWEET-TREND"

    # 2. โหมดรสเปรี้ยว (SOUR -> กวาดสภาพคล่องกรอบเอเชียแล้วความเร่งดีดกลับเข้ากรอบ)
    if flavor == "SOUR":
        if info["swept_low"] and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 54):
            if h4_bull or h1_bull:
                return "BUY", "SOUR-TRAP"

        if info["swept_high"] and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 46):
            if h4_bear or h1_bear:
                return "SELL", "SOUR-TRAP"

    # 3. โหมดรสเค็ม (SALTY -> ดักเด้งในกรอบ CHOP > 61.8 เฉพาะฝั่งเดียวกับโครงสร้างใหญ่ H4 เท่านั้น!)
    if flavor == "SALTY":
        # ดัก BUY ที่ขอบล่างของกรอบไซด์เวย์ เฉพาะเมื่อโครงสร้างใหญ่ H4 เป็นขาขึ้น
        if h4_bull and (info["prev_z"] <= -1.35) and (p_accel > 0.0) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 48):
            return "BUY", "SALTY-MR"

        # ดัก SELL ที่ขอบบนของกรอบไซด์เวย์ เฉพาะเมื่อโครงสร้างใหญ่ H4 เป็นขาลง
        if h4_bear and (info["prev_z"] >= 1.35) and (p_accel < 0.0) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 52):
            return "SELL", "SALTY-MR"

    return None, ""
