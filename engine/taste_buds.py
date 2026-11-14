def taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars):
    """
    ต่อมรับรสแบบปรับตัวตามสภาพแวดล้อม (Adaptive Homeostasis Taste Buds):
    ไม่ใช้ตัวเลขคงที่ตายตัว แต่เปรียบเทียบค่าปัจจุบันกับฐานค่าเฉลี่ยย้อนหลัง 100 แท่ง (Dynamic Quantiles)
    """
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

    # 1. รสขม (BITTER): ความผันผวนกระชากผิดธรรมชาติ หรือตลาดไร้ชีพจร
    if atr_ratio > 1.85 or atr_ratio < 0.45:
        return "BITTER", {"reason": "TOXIC_VOLATILITY"}

    # 2. รสเปรี้ยว (SOUR): ตลาดเพิ่งกวาดสภาพคล่องขอบกรอบเอเชีย (Sweep & Reject)
    has_asian_box = (asian_bars >= 8) and (asian_high > asian_low)
    if has_asian_box:
        swept_low = ((float(bar["low"]) < asian_low) or (float(prev["low"]) < asian_low)) and (float(bar["close"]) > asian_low)
        swept_high = ((float(bar["high"]) > asian_high) or (float(prev["high"]) > asian_high)) and (float(bar["close"]) < asian_high)
        if swept_low or swept_high:
            return "SOUR", {
                "swept_low": swept_low,
                "swept_high": swept_high,
                "prev_z": prev_z
            }

    # 3. รสหวาน (SWEET): เทรนด์ไหลลื่น (H1+H4 เรียงตัว และค่า ER สูงกว่าค่ากลางของสภาพแวดล้อมช่วงนั้น)
    if mtf_aligned and (er_v >= er_med):
        return "SWEET", {
            "bull_trend": (h1_bull and h4_bull),
            "bear_trend": (h1_bear and h4_bear),
            "er": er_v,
            "strong_trend": (er_v >= er_q65)
        }

    # 4. รสเค็ม (SALTY): ตลาดแกว่งในกรอบ และราคาดีดทะลุกรอบ Dynamic Z-Band (z_up / z_dn) ของช่วงนั้น
    if (er_v < er_q65) and (prev_z <= z_dn or prev_z >= z_up):
        return "SALTY", {
            "prev_z": prev_z,
            "z_up": z_up,
            "z_dn": z_dn
        }

    return "BITTER", {"reason": "NO_DISTINCT_FLAVOR"}
