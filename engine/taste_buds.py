def taste_market_flavor(bar, prev, asian_high=None, asian_low=None, asian_bars=0):
    """
    สวิตช์คัดกรองสภาวะตลาด V14.4:
    คลายเกณฑ์ SOUR (WR 64.7%) และ SALTY (WR 58.8%) เล็กน้อยเพื่อเพิ่มจำนวนวันออกไม้ให้สม่ำเสมอขึ้น
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

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])
    mtf_aligned = (h1_bull and h4_bull) or (h1_bear and h4_bear)

    has_macro_expansion = bool(bar.get("macro_bull_conv", False)) or bool(bar.get("macro_bear_conv", False))

    # 1. รสขม (BITTER): กรอบความผันผวนปลอดภัย 0.48 - 1.82
    if atr_ratio > 1.82 or atr_ratio < 0.48:
        return "BITTER", {"reason": "TOXIC_VOLATILITY"}

    # 2. รสเปรี้ยว (SOUR): พระเอกทำกำไรอันดับ 1 ในไฟล์ 39 (+$2,026.87 / WR 64.71%)
    ref_high = max(float(asian_high), struct_h) if (asian_bars >= 8 and asian_high > asian_low) else struct_h
    ref_low = min(float(asian_low), struct_l) if (asian_bars >= 8 and asian_high > asian_low) else struct_l

    if (ref_high > ref_low) and (atr_ratio <= 1.28):
        swept_low = ((low_p < ref_low) or (float(prev["low"]) < ref_low)) and (close_p > ref_low) and (p_accel >= 0.03)
        swept_high = ((high_p > ref_high) or (float(prev["high"]) > ref_high)) and (close_p < ref_high) and (p_accel <= -0.03)
        if swept_low or swept_high:
            return "SOUR", {
                "swept_low": swept_low,
                "swept_high": swept_high
            }

    # 3. รสเค็ม (SALTY): พระเอกทำกำไรอันดับ 2 ในไฟล์ 39 (+$1,092.75 / WR 58.82%)
    # ขยายให้รับตั้งแต่ CHOP >= 48.5 และ |prev_z| >= 1.42 เพื่อเก็บไม้ในวันที่ตลาดแกว่งแคบได้มากขึ้น
    if (not has_macro_expansion) and (chop_v >= 48.5) and (abs(prev_z) >= 1.42):
        return "SALTY", {
            "prev_z": prev_z
        }

    # 4. รสหวาน (SWEET): เทรนด์ H1+H4 เรียงตัวสอดคล้องกัน และ CHOP < 50.0
    if (chop_v < 50.0) and mtf_aligned:
        return "SWEET", {
            "bull_trend": (h1_bull and h4_bull),
            "bear_trend": (h1_bear and h4_bear),
            "chop": chop_v,
            "kama_slope": kama_slope,
            "atr_ratio": atr_ratio
        }

    return "BITTER", {"reason": "NO_DISTINCT_FLAVOR"}
