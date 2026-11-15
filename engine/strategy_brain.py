from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนกลาง V14.1 (100% Mathematical Decision - No Hour-of-Day Lock):
    - แทนที่การเช็กชั่วโมง (t_hour in 9, 15, 16, 20, 21) ใน SWEET-VWAP ด้วยสมการคณิตศาสตร์ของแรงส่งจริง:
      1) CHOP < 38.2 (Fibonacci Pure Trend) หรือ
      2) มีพลังงานสถาบันหนุนหลัง (+OI: has_macro_expansion) หรือ
      3) ความผันผวนสัมพัทธ์ขยายตัว (atr_ratio >= 0.88) พร้อมความชันแคลคูลัส KAMA ชี้ไปทางเดียวกับเทรนด์
    """
    t_mins = int(bar["thai_mins"])
    if not ((9 * 60 + 30) <= t_mins <= (21 * 60 + 45)):
        return None, ""

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    vwrsi_v = float(bar["vwrsi"])
    prev_rsi = float(prev["vwrsi"])
    p_accel = float(bar.get("price_accel", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars)

    if flavor == "BITTER":
        return None, ""

    # 1. รสหวาน (SWEET -> ใช้สมการคณิตศาสตร์คัดกรองแรงส่งจริงแทนการล็อกชั่วโมงเวลา)
    if flavor == "SWEET":
        chop_v = float(info.get("chop", 50.0))
        k_slope = float(info.get("kama_slope", 0.0))
        atr_r = float(info.get("atr_ratio", 1.0))
        has_oi = bool(info.get("has_macro_expansion", False))

        # สมการยืนยันการขยายตัวของเทรนด์ (Mathematical Expansion Filter แทนการดูนาฬิกา)
        math_bull_expansion = (chop_v < 38.2) or has_oi or (atr_r >= 0.88 and k_slope >= 0.025)
        math_bear_expansion = (chop_v < 38.2) or has_oi or (atr_r >= 0.88 and k_slope <= -0.025)

        # ท่าที่ 1A: SWEET-VWAP (ราคาย่อแตะเส้น VWAP แล้วดีดกลับด้วยโมเมนตัมจริง)
        if info["bull_trend"] and math_bull_expansion and (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p) and (close_p > open_p):
            if (50 <= vwrsi_v <= 70) and (vwrsi_v > prev_rsi):
                return "BUY", "SWEET-VWAP"

        if info["bear_trend"] and math_bear_expansion and (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p) and (close_p < open_p):
            if (30 <= vwrsi_v <= 50) and (vwrsi_v < prev_rsi):
                return "SELL", "SWEET-VWAP"

        # ท่าที่ 1B: SWEET-EV (พักตัว 1 แท่งแล้วเกิดความเร่งอนุพันธ์อันดับ 2 ส่งไปต่อตามเทรนด์)
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])
        if info["bull_trend"] and math_bull_expansion and prev_red and (close_p > open_p) and (close_p > vwap_p) and (p_accel > 0.0) and (52 <= vwrsi_v <= 68):
            return "BUY", "SWEET-EV"
        if info["bear_trend"] and math_bear_expansion and prev_green and (close_p < open_p) and (close_p < vwap_p) and (p_accel < 0.0) and (32 <= vwrsi_v <= 48):
            return "SELL", "SWEET-EV"

    # 2. รสเปรี้ยว (SOUR -> ดักสวนกับดักกวาดสภาพคล่องเมื่อความเร่งพลิกกลับ)
    if flavor == "SOUR":
        if info["swept_low"] and (close_p > open_p) and (vwrsi_v > prev_rsi) and (30 <= vwrsi_v <= 55):
            if h4_bull:
                return "BUY", "SOUR-TRAP"

        if info["swept_high"] and (close_p < open_p) and (vwrsi_v < prev_rsi) and (45 <= vwrsi_v <= 70):
            if not (h1_bull and h4_bull):
                return "SELL", "SOUR-TRAP"

    # 3. รสเค็ม (SALTY -> ดักเด้งไซด์เวย์เฉพาะวันที่ไม่มี +OI ดันเทรนด์ และไม่สวนโครงสร้างใหญ่ H4)
    if flavor == "SALTY":
        if h4_bull and (info["prev_z"] <= -1.50) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 46):
            return "BUY", "SALTY-MR"

        if h4_bear and (info["prev_z"] >= 1.50) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 54):
            return "SELL", "SALTY-MR"

    return None, ""
