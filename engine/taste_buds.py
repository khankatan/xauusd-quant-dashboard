def taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars):
    """
    ต่อมรับรสแบบปรับตัวตามสภาพแวดล้อม V11.1 (Bio-Sensory Homeostasis):
    1. BITTER (ขม): ความผันผวนกระชากผิดธรรมชาติ (> 1.85x) หรือตลาดไร้ชีพจร (< 0.50x)
    2. SWEET (หวาน): เทรนด์จริงต้องมีทั้งทิศทาง (H1+H4), ความเรียบของเทรนด์ (er >= er_q65)
       และพลังงานตลาดหนุนหลัง (atr_ratio >= 0.85) เพื่อไม่ให้หลงกลเทรนด์หลอกช่วงตลาดซึม
    3. SOUR (เปรี้ยว): กับดักกวาดสภาพคล่องขอบ Asian Box เฉพาะช่วงที่กรอบยังสดใหม่
       และพลังงานไม่พุ่งทะลุกรอบแบบ Breakout จริง (atr_ratio <= 1.25)
    4. SALTY (เค็ม): ตลาดแกว่งตัวในกรอบ (er < er_q65) และราคาฉีกออกนอก Dynamic Z-Band
    """
    t_mins = int(bar["thai_mins"])
    atr_ratio = float(bar.get("atr_ratio", 1.0))
    er_v = float(bar.get("er", 0.25))
    er_med = float(bar.get("er_med", 0.25))
    er_q65 = float(bar.get("er_q65", 0.32))

    prev_z = float(prev.get("fast_z", 0.0))
    z_up = float(bar.get("z_upper_dyn", 1.65))
    z_dn = float(bar.get("z_lower_dyn", -1.65))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])
    mtf_aligned = (h1_bull and h4_bull) or (h1_bear and h4_bear)

    # 1. รสขม (BITTER): พิษตลาด
    if atr_ratio > 1.85 or atr_ratio < 0.50:
        return "BITTER", {"reason": "TOXIC_VOLATILITY"}

    # 2. รสหวาน (SWEET): เทรนด์แท้ ต้องมีทั้งความเรียงตัว (er >= er_q65) และพลังงานวอลุ่ม (atr_ratio >= 0.85)
    # หากพลังงานต่ำกว่า 0.85 (เช่น ช่วงซึม 10:00-12:59 น.) ต้องมี er สูงระดับพรีเมียมเท่านั้นจึงจะนับเป็นเทรนด์
    min_er_for_sweet = er_q65 if atr_ratio >= 0.90 else (er_q65 * 1.25)
    if mtf_aligned and (er_v >= min_er_for_sweet) and (atr_ratio >= 0.78):
        return "SWEET", {
            "bull_trend": (h1_bull and h4_bull),
            "bear_trend": (h1_bear and h4_bear),
            "er": er_v,
            "strong_trend": True
        }

    # 3. รสเปรี้ยว (SOUR): กับดักกวาดสภาพคล่องขอบ Asian Box
    # ทำงานเมื่อกรอบเอเชียสร้างเสร็จและยังไม่ถูกพลังงานฝั่งอเมริกา (หลัง 18:00 น. หรือ atr_ratio > 1.25) ทุบทำลายกรอบ
    has_asian_box = (asian_bars >= 8) and (asian_high > asian_low)
    box_still_fresh = (t_mins < 18 * 60) and (atr_ratio <= 1.28)
    if has_asian_box and box_still_fresh:
        swept_low = ((float(bar["low"]) < asian_low) or (float(prev["low"]) < asian_low)) and (float(bar["close"]) > asian_low)
        swept_high = ((float(bar["high"]) > asian_high) or (float(prev["high"]) > asian_high)) and (float(bar["close"]) < asian_high)
        if swept_low or swept_high:
            return "SOUR", {
                "swept_low": swept_low,
                "swept_high": swept_high,
                "prev_z": prev_z
            }

    # 4. รสเค็ม (SALTY): ตลาดไซด์เวย์ไร้เทรนด์ และราคาดีดทะลุกรอบ Dynamic Z-Band
    if (er_v < er_q65) and (prev_z <= z_dn or prev_z >= z_up):
        return "SALTY", {
            "prev_z": prev_z,
            "z_up": z_up,
            "z_dn": z_dn
        }

    return "BITTER", {"reason": "NO_DISTINCT_FLAVOR"}
