def taste_market_flavor(bar, prev, asian_high=None, asian_low=None, asian_bars=0, trades_today=0):
    """
    ระบบประสาทรับรสแบบสมองสองซีก V15.3 (File 42 Record Winner Core + Dynamic TK Support):
    - ยึดโครงสร้างของไฟล์ 42 (ที่ทำกำไร +$3,228.84 / WR 53.45% / MaxDD 2.12%) เป็นแกนหลัก 100%
    - เสริมความแม่นยำด้วยการจัดเรียงตัวของเส้น Dynamic Tenkan-sen และ Kijun-sen
    """
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
    tenkan_p = float(bar.get("tenkan", close_p))
    kijun_p = float(bar.get("kijun", close_p))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])
    mtf_aligned = (h1_bull and h4_bull) or (h1_bear and h4_bear)

    has_macro_expansion = bool(bar.get("macro_bull_conv", False)) or bool(bar.get("macro_bear_conv", False))

    # 1. รสขม (BITTER): ตลาดผันผวนกระชากผิดธรรมชาติ หรือตลาดไร้สภาพคล่อง
    if atr_ratio > 1.82 or atr_ratio < 0.48:
        return "BITTER", {"reason": "TOXIC_VOLATILITY"}

    ref_high = max(float(asian_high), struct_h) if (asian_bars >= 8 and asian_high > asian_low) else struct_h
    ref_low = min(float(asian_low), struct_l) if (asian_bars >= 8 and asian_high > asian_low) else struct_l

    # 2. รสเปรี้ยว (SOUR): แชมป์ทำเงินอันดับ 1 ในไฟล์ 42 (+$3,809.24 / WR 67.74%)
    if (ref_high > ref_low) and (atr_ratio <= 1.30):
        raw_swept_low = ((low_p < ref_low) or (float(prev["low"]) < ref_low)) and (close_p > ref_low)
        raw_swept_high = ((high_p > ref_high) or (float(prev["high"]) > ref_high)) and (close_p < ref_high)

        left_sour_low = raw_swept_low and (atr_ratio <= 1.25) and (p_accel >= 0.08)
        left_sour_high = raw_swept_high and (atr_ratio <= 1.25) and (p_accel <= -0.08)

        has_asian = (asian_bars >= 8) and (asian_high > asian_low)
        right_sour_low = has_asian and ((low_p < float(asian_low)) or (float(prev["low"]) < float(asian_low))) and (close_p > float(asian_low)) and (p_accel > 0.0)
        right_sour_high = has_asian and ((high_p > float(asian_high)) or (float(prev["high"]) > float(asian_high))) and (close_p < float(asian_high)) and (p_accel < 0.0)

        if left_sour_low or left_sour_high or right_sour_low or right_sour_high:
            return "SOUR", {
                "swept_low": (left_sour_low or right_sour_low),
                "swept_high": (left_sour_high or right_sour_high),
                "hemisphere": "L" if (left_sour_low or left_sour_high) else "R"
            }

    # 3. รสเค็ม (SALTY): สมองซีกซ้ายคุมกรอบไซด์เวย์ (CHOP >= 50 & |prev_z| >= 1.55 -> +$762.89 ในไฟล์ 42)
    if (not has_macro_expansion) and (chop_v >= 50.0) and (abs(prev_z) >= 1.55):
        return "SALTY", {
            "prev_z": prev_z,
            "hemisphere": "L"
        }

    # 4. รสหวาน (SWEET): ประสานสมองซีกซ้าย + ซีกขวา พร้อมค่า Dynamic Tenkan/Kijun
    if (chop_v < 54.0) and mtf_aligned:
        return "SWEET", {
            "bull_trend": (h1_bull and h4_bull),
            "bear_trend": (h1_bear and h4_bear),
            "tk_bull": (tenkan_p >= kijun_p),
            "tk_bear": (tenkan_p <= kijun_p),
            "chop": chop_v,
            "kama_slope": kama_slope,
            "atr_ratio": atr_ratio,
            "has_macro_expansion": has_macro_expansion
        }

    return "BITTER", {"reason": "NO_DISTINCT_FLAVOR"}
