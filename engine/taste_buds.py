def taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars):
    """
    ต่อมรับรส V12.1 (Fibonacci CHOP 38.2 / 61.8 + CHOP Derivative Routing):
    1. BITTER: ความผันผวนฉีกขาดช่วงข่าวกระชาก (atr_ratio > 1.90) หรือตลาดไร้ชีพจร (< 0.45)
    2. SOUR (Trap): กวาดสภาพคล่อง Asian Box หรือขอบ Swing Structure แล้วเกิดความเร่งสวนกลับ
    3. SWEET (Trend): CHOP < 38.2 (เทรนด์เต็มตัว) หรือ CHOP กำลังดิ่งลงแรง (d_chop <= -2.0 = ต้นคลื่นเทรนด์ใหม่)
    4. SALTY (Range): CHOP > 61.8 (ไซด์เวย์เต็มตัว) หรือ CHOP >= 54.0 ที่กำลังบีบตัวขึ้น (d_chop >= 0)
    """
    t_mins = int(bar["thai_mins"])
    atr_ratio = float(bar.get("atr_ratio", 1.0))
    chop_v = float(bar.get("chop", 50.0))
    prev_chop = float(prev.get("chop", 50.0))
    d_chop = chop_v - prev_chop  # อนุพันธ์ของ CHOP: ติดลบ = กำลังระเบิดเทรนด์, เป็นบวก = กำลังบีบไซด์เวย์

    slope_v = float(bar.get("slope", 0.0))
    accel_v = float(bar.get("accel", 0.0))
    p_accel = float(bar.get("price_accel", 0.0))
    prev_z = float(prev.get("fast_z", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    # 1. รสขม (BITTER): ตลาดผันผวนสุดโต่งเกินเพดาน หรือตลาดตาย
    if atr_ratio > 1.90 or atr_ratio < 0.45:
        return "BITTER", {"reason": "EXTREME_VOLATILITY"}

    # 2. รสเปรี้ยว (SOUR): กวาดสภาพคล่อง Asian Box + แคลคูลัสความเร่งพลิกกลับ (พระเอกทำเงิน +$1,762 ใน V12)
    has_asian_box = (asian_bars >= 8) and (asian_high > asian_low) and (t_mins < 19 * 60)
    if has_asian_box and (atr_ratio <= 1.35):
        swept_low = ((float(bar["low"]) < asian_low) or (float(prev["low"]) < asian_low)) and (float(bar["close"]) > asian_low)
        swept_high = ((float(bar["high"]) > asian_high) or (float(prev["high"]) > asian_high)) and (float(bar["close"]) < asian_high)
        if (swept_low and p_accel > 0) or (swept_high and p_accel < 0):
            return "SOUR", {
                "swept_low": swept_low,
                "swept_high": swept_high
            }

    # 3. รสหวาน (SWEET): CHOP < 38.2 (Fibonacci Trend Zone) หรือ CHOP กำลังหดตัวลงสู่เทรนด์ใหม่ (chop < 48 & d_chop < -1.2)
    bull_aligned = h1_bull and h4_bull and (slope_v > 0.015)
    bear_aligned = h1_bear and h4_bear and (slope_v < -0.015)
    is_fibonacci_trend = (chop_v < 38.2) or (chop_v < 48.0 and d_chop <= -1.2)

    if is_fibonacci_trend and (bull_aligned or bear_aligned) and (atr_ratio >= 0.80):
        return "SWEET", {
            "bull_trend": bull_aligned,
            "bear_trend": bear_aligned,
            "slope": slope_v,
            "accel": accel_v
        }

    # 4. รสเค็ม (SALTY): CHOP > 61.8 (Fibonacci Sideways Zone) หรือ CHOP >= 54.0 ที่กำลังสะสมพลัง (d_chop >= 0)
    is_fibonacci_range = (chop_v > 61.8) or (chop_v >= 54.0 and d_chop >= 0.0)
    if is_fibonacci_range and (abs(prev_z) >= 1.35):
        return "SALTY", {
            "prev_z": prev_z,
            "p_accel": p_accel
        }

    return "BITTER", {"reason": "TRANSITION_DEAD_ZONE"}
