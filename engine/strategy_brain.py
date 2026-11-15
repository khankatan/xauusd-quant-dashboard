from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนกลาง V14.2 (Tuned Pure Mathematical Filter):
    - ตัด `or has_oi` Bypass ออก! (ในไฟล์ 37 ไม้ที่ผ่าน Pure Math ชนะ 52.89% กำไร +$1,368.68
      แต่ไม้ที่ลัดคิวผ่าน `or has_oi` แพ้ถึง 68.6% ขาดทุน -$4,221.36)
    - ทุกไม้ของ SWEET ต้องผ่านเกณฑ์ CHOP < 38.2 หรือ (atr_ratio >= 0.90 และ |kama_slope| >= 0.03) เท่านั้น
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
    p_accel = float(bar.get("price_accel", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars)

    if flavor == "BITTER":
        return None, ""

    # 1. รสหวาน (SWEET -> ต้องผ่านสมการ Pure Math Expansion เท่านั้น ห้ามใช้ has_oi ลัดคิว!)
    if flavor == "SWEET":
        chop_v = float(info.get("chop", 50.0))
        k_slope = float(info.get("kama_slope", 0.0))
        atr_r = float(info.get("atr_ratio", 1.0))

        math_bull_expansion = ((chop_v < 38.2) and (k_slope > 0.01)) or ((atr_r >= 0.90) and (k_slope >= 0.03))
        math_bear_expansion = ((chop_v < 38.2) and (k_slope < -0.01)) or ((atr_r >= 0.90) and (k_slope <= -0.03))

        # SWEET-VWAP: ย่อแตะเส้น VWAP แล้วดีดกลับตามเทรนด์พร้อมความชัน KAMA หนุนหลัง
        if info["bull_trend"] and math_bull_expansion and (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p) and (close_p > open_p):
            if (52 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (fast_z <= 1.05):
                return "BUY", "SWEET-VWAP"

        if info["bear_trend"] and math_bear_expansion and (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p) and (close_p < open_p):
            if (32 <= vwrsi_v <= 48) and (vwrsi_v < prev_rsi) and (fast_z >= -1.05):
                return "SELL", "SWEET-VWAP"

        # SWEET-EV: พักตัว 1 แท่งแล้วเกิดความเร่งอนุพันธ์อันดับ 2 พุ่งต่อตามเทรนด์เหนือทั้ง VWAP และ KAMA
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])
        if info["bull_trend"] and math_bull_expansion and prev_red and (close_p > open_p) and (close_p > vwap_p) and (close_p > kama_p):
            if (p_accel >= 0.05) and (53 <= vwrsi_v <= 66) and (fast_z <= 1.00):
                return "BUY", "SWEET-EV"

        if info["bear_trend"] and math_bear_expansion and prev_green and (close_p < open_p) and (close_p < vwap_p) and (close_p < kama_p):
            if (p_accel <= -0.05) and (34 <= vwrsi_v <= 47) and (fast_z >= -1.00):
                return "SELL", "SWEET-EV"

    # 2. รสเปรี้ยว (SOUR -> ดักสวนกับดักกวาดสภาพคล่องตามทิศทางโครงสร้างใหญ่ H4)
    if flavor == "SOUR":
        if info["swept_low"] and h4_bull and (close_p > open_p) and (vwrsi_v > prev_rsi) and (30 <= vwrsi_v <= 52):
            return "BUY", "SOUR-TRAP"

        if info["swept_high"] and h4_bear and (close_p < open_p) and (vwrsi_v < prev_rsi) and (48 <= vwrsi_v <= 70):
            return "SELL", "SOUR-TRAP"

    # 3. รสเค็ม (SALTY -> ดักเด้งไซด์เวย์ตามทิศทางโครงสร้างใหญ่ H4)
    if flavor == "SALTY":
        if h4_bull and (info["prev_z"] <= -1.55) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 45):
            return "BUY", "SALTY-MR"

        if h4_bear and (info["prev_z"] >= 1.55) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 55):
            return "SELL", "SALTY-MR"

    return None, ""
