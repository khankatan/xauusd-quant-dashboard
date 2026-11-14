def taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars):
    """
    ต่อมรับรสของตลาด (Market Tongue Sensor):
    ชิมพฤติกรรมราคาจริง ณ แท่งปัจจุบัน แล้วส่งรหัสรสชาติให้สมองส่วนกลาง
    """
    atr_ratio = float(bar.get("atr_ratio", 1.0))
    er_v = float(bar.get("er", 0.30))
    prev_z = float(prev.get("fast_z", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])
    mtf_aligned = (h1_bull and h4_bull) or (h1_bear and h4_bear)

    # 1. รสขม (BITTER): ตลาดผันผวนกระชากผิดปกติ หรือนิ่งสนิท -> งดเทรด
    if atr_ratio > 1.85 or atr_ratio < 0.45:
        return "BITTER", {"reason": "TOXIC_VOLATILITY"}

    # 2. รสหวาน (SWEET): เทรนด์สะอาด H1+H4 เรียงตัว + ER >= 0.35 -> ส่งให้สมองตามเทรนด์
    if mtf_aligned and (er_v >= 0.35):
        return "SWEET", {
            "bull_trend": (h1_bull and h4_bull),
            "bear_trend": (h1_bear and h4_bear),
            "er": er_v
        }

    # 3. รสเปรี้ยว (SOUR): ตลาดทำกับดักกวาด High/Low กรอบเอเชียแล้วดีดกลับเข้ากรอบ
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

    # 4. รสเค็ม (SALTY): ตลาดไซด์เวย์ไร้เทรนด์ (ER < 0.35) และราคาฉีกออกนอกกรอบ Z-Score
    if (er_v < 0.35) and (abs(prev_z) >= 1.60):
        return "SALTY", {
            "prev_z": prev_z,
            "er": er_v
        }

    return "BITTER", {"reason": "NO_DISTINCT_FLAVOR"}
