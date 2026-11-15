def taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars):
    """
    สวิตช์คัดกรองสภาวะตลาด V13 (Adaptive CHOP Regime Switch):
    - BITTER: ตลาดผันผวนกระชากผิดปกติ (atr_ratio > 1.85) หรือตลาดนิ่งสนิท (< 0.45)
    - SOUR (Trap): กวาดขอบ Asian High/Low ในช่วงบ่ายลอนดอน (14:00-17:45 น.) ที่ทำกำไร +$1,762 ในไฟล์ 32
    - SALTY (Sideways MR): เมื่อ Adaptive CHOP >= 54.0 (ตลาดบีบตัวไซด์เวย์) และราคาฉีกเกิน |prev_z| >= 1.60 (สูตรทำเงินของไฟล์ 29)
    - SWEET (Trend VWAP/EV): เมื่อตลาดไม่ไซด์เวย์หนัก (CHOP < 54.0) และ H1+H4 เรียงตัวไปทางเดียวกัน (สูตรทำเงินของไฟล์ 25/26)
    """
    t_mins = int(bar["thai_mins"])
    atr_ratio = float(bar.get("atr_ratio", 1.0))
    chop_v = float(bar.get("chop", 50.0))
    prev_z = float(prev.get("fast_z", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])
    mtf_aligned = (h1_bull and h4_bull) or (h1_bear and h4_bear)

    # 1. รสขม (BITTER): ข่าวกระชากผิดธรรมชาติ หรือตลาดไร้ชีพจร
    if atr_ratio > 1.85 or atr_ratio < 0.45:
        return "BITTER", {"reason": "TOXIC_VOLATILITY"}

    # 2. รสเปรี้ยว (SOUR): กับดักกวาดสภาพคล่อง Asian Box ช่วงบ่าย-เย็น (14:00 - 17:45 น.)
    has_asian_box = (asian_bars >= 8) and (asian_high > asian_low) and ((14 * 60) <= t_mins <= (17 * 60 + 45))
    if has_asian_box and (atr_ratio <= 1.30):
        swept_low = ((float(bar["low"]) < asian_low) or (float(prev["low"]) < asian_low)) and (float(bar["close"]) > asian_low)
        swept_high = ((float(bar["high"]) > asian_high) or (float(prev["high"]) > asian_high)) and (float(bar["close"]) < asian_high)
        if swept_low or swept_high:
            return "SOUR", {
                "swept_low": swept_low,
                "swept_high": swept_high
            }

    # 3. รสเค็ม (SALTY): เมื่อตลาดเป็นไซด์เวย์ (CHOP >= 54.0) และราคาฉีกออกนอกกรอบ |prev_z| >= 1.60
    if (chop_v >= 54.0) and (abs(prev_z) >= 1.60):
        return "SALTY", {
            "prev_z": prev_z
        }

    # 4. รสหวาน (SWEET): เมื่อตลาดเป็นเทรนด์ (CHOP < 54.0) และ H1+H4 เรียงตัวสอดคล้องกัน
    if (chop_v < 54.0) and mtf_aligned:
        return "SWEET", {
            "bull_trend": (h1_bull and h4_bull),
            "bear_trend": (h1_bear and h4_bear)
        }

    return "BITTER", {"reason": "NO_DISTINCT_FLAVOR"}
