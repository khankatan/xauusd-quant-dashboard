def taste_market_flavor(bar, prev, asian_high=None, asian_low=None, asian_bars=0, trades_today=0):
    """
    ระบบประสาทรับรสแบบสมองสองซีก V15.1 (Dual-Hemisphere + Daily Quota Filler):
    - ซีกซ้าย (Left Hemisphere): ทำงานตลอดวันด้วยเกณฑ์เข้มงวดระดับ Sniper (จากไฟล์ 39/42)
    - ซีกขวา (Right Hemisphere): ช่วยเก็บจังหวะ Contextual Flow และหากหลัง 15:00 น. วันนี้ยังไม่มีออเดอร์ (trades_today == 0)
      จะเปิดโหมด Daily Filler เพื่อจับจังหวะย่อในกรอบแคบ ไม่ให้พลาดการออกไม้รายวัน
    """
    t_mins = int(bar["thai_mins"])
    atr_ratio = float(bar.get("atr_ratio", 1.0))
    chop_v = float(bar.get("chop", 50.0))
    prev_z = float(prev.get("fast_z", 0.0))
    kama_slope = float(bar.get("kama_slope", 0.0))
    p_accel = float(bar.get("price_accel", 0.0))

    close_p = float(bar["close"])
    high_p = float(bar["high"])
    low_p = float(bar["low"])
    struct_h = float(bar.get("struct_high", high_p))
    struct_l = float(bar.get("struct_low", low_p))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])
    mtf_aligned = (h1_bull and h4_bull) or (h1_bear and h4_bear)

    has_macro_expansion = bool(bar.get("macro_bull_conv", False)) or bool(bar.get("macro_bear_conv", False))

    # โหมดเร่งสแกนหาไม้ประจำวัน: เมื่อหลัง 15:00 น. แล้ววันนี้ยังไม่ได้ออกไม้เลย (trades_today == 0)
    need_daily_trade = (trades_today == 0) and (t_mins >= 15 * 60)

    # 1. รสขม (BITTER): ตลาดผันผวนกระชากผิดธรรมชาติ หรือตลาดไร้ชีพจร
    min_atr_r = 0.42 if need_daily_trade else 0.48
    if atr_ratio > 1.85 or atr_ratio < min_atr_r:
        return "BITTER", {"reason": "TOXIC_VOLATILITY"}

    # ขอบอ้างอิงโครงสร้าง (ผสานกรอบเอเชียและกรอบวัฏจักร Hilbert)
    ref_high = max(float(asian_high), struct_h) if (asian_bars >= 8 and asian_high > asian_low) else struct_h
    ref_low = min(float(asian_low), struct_l) if (asian_bars >= 8 and asian_high > asian_low) else struct_l

    # =========================================================================
    # 2. รสเปรี้ยว (SOUR): แชมป์ทำเงินอันดับ 1 ในไฟล์ 42 (+$3,809.24 / WR 67.74%)
    # =========================================================================
    if (ref_high > ref_low) and (atr_ratio <= 1.32):
        raw_swept_low = ((low_p < ref_low) or (float(prev["low"]) < ref_low)) and (close_p > ref_low)
        raw_swept_high = ((high_p > ref_high) or (float(prev["high"]) > ref_high)) and (close_p < ref_high)

        left_sour_low = raw_swept_low and (atr_ratio <= 1.25) and (p_accel >= 0.08)
        left_sour_high = raw_swept_high and (atr_ratio <= 1.25) and (p_accel <= -0.08)

        has_asian = (asian_bars >= 8) and (asian_high > asian_low)
        right_sour_low = (has_asian or need_daily_trade) and raw_swept_low and (p_accel > 0.0)
        right_sour_high = (has_asian or need_daily_trade) and raw_swept_high and (p_accel < 0.0)

        if left_sour_low or left_sour_high or right_sour_low or right_sour_high:
            return "SOUR", {
                "swept_low": (left_sour_low or right_sour_low),
                "swept_high": (left_sour_high or right_sour_high),
                "hemisphere": "L" if (left_sour_low or left_sour_high) else "R"
            }

    # =========================================================================
    # 3. รสเค็ม (SALTY): ซีกซ้ายใช้ |prev_z| >= 1.55 / ซีกขวาช่วยเก็บวันที่ยังไม่มีไม้ด้วย |prev_z| >= 1.28
    # =========================================================================
    if not has_macro_expansion:
        if (chop_v >= 50.0) and (abs(prev_z) >= 1.55):
            return "SALTY", {"prev_z": prev_z, "hemisphere": "L"}
        if need_daily_trade and (chop_v >= 46.0) and (abs(prev_z) >= 1.28):
            return "SALTY", {"prev_z": prev_z, "hemisphere": "R"}

    # =========================================================================
    # 4. รสหวาน (SWEET): เทรนด์ H1+H4 เรียงตัวสอดคล้องกัน (หรือ H4 นำทางในโหมด Daily Filler)
    # =========================================================================
    if (chop_v < 54.0) and mtf_aligned:
        return "SWEET", {
            "bull_trend": (h1_bull and h4_bull),
            "bear_trend": (h1_bear and h4_bear),
            "chop": chop_v,
            "kama_slope": kama_slope,
            "atr_ratio": atr_ratio,
            "has_macro_expansion": has_macro_expansion,
            "need_daily_trade": need_daily_trade
        }

    # หากหลัง 15:00 น. ยังไม่มีไม้ และ H1 กับ H4 ขัดแย้งกัน ให้ยึดโครงสร้างใหญ่ H4 คู่กับความชัน KAMA
    if need_daily_trade and (chop_v < 50.0):
        if (h4_bull and kama_slope >= 0.02) or (h4_bear and kama_slope <= -0.02):
            return "SWEET", {
                "bull_trend": (h4_bull and kama_slope >= 0.02),
                "bear_trend": (h4_bear and kama_slope <= -0.02),
                "chop": chop_v,
                "kama_slope": kama_slope,
                "atr_ratio": atr_ratio,
                "has_macro_expansion": has_macro_expansion,
                "need_daily_trade": True
            }

    return "BITTER", {"reason": "NO_DISTINCT_FLAVOR"}
