def taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars):
    """
    ขั้นตอนที่ 3: คัดกรองสภาวะตลาด (Strategy Routing) ด้วย Adaptive CHOP + KAMA Calculus
    - BITTER: ความผันผวนฉีกขาดช่วงข่าวกระชาก (atr_ratio > 1.90) หรือตลาดไร้ชีพจร (< 0.45)
    - SWEET (Trend): Adaptive CHOP < 46.5 + ความชัน KAMA (Slope) สอดคล้องกับเทรนด์ใหญ่ H1 & H4
    - SOUR (Liquidity Trap): กวาดขอบ Asian High/Low แล้วเกิดความเร่งสวนกลับ (Calculus Reversal Acceleration)
    - SALTY (Range MR): Adaptive CHOP >= 52.0 (ตลาดสะสมพลังในกรอบ) และราคาฉีกออกจากเส้น KAMA
    """
    t_mins = int(bar["thai_mins"])
    atr_ratio = float(bar.get("atr_ratio", 1.0))
    chop_v = float(bar.get("chop", 50.0))
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

    # 2. รสเปรี้ยว (SOUR): กวาดสภาพคล่อง Asian Box + แคลคูลัสความเร่งพลิกกลับ (Reversal Acceleration)
    has_asian_box = (asian_bars >= 8) and (asian_high > asian_low) and (t_mins < 18 * 60)
    if has_asian_box and (atr_ratio <= 1.30):
        swept_low = ((float(bar["low"]) < asian_low) or (float(prev["low"]) < asian_low)) and (float(bar["close"]) > asian_low)
        swept_high = ((float(bar["high"]) > asian_high) or (float(prev["high"]) > asian_high)) and (float(bar["close"]) < asian_high)
        if (swept_low and p_accel > 0) or (swept_high and p_accel < 0):
            return "SOUR", {
                "swept_low": swept_low,
                "swept_high": swept_high
            }

    # 3. รสหวาน (SWEET): Adaptive CHOP ต่ำ (< 46.5 = ตลาดมีทิศทางชัดเจน) + KAMA Slope วิ่งตามเทรนด์ใหญ่ H1 & H4
    bull_aligned = h1_bull and h4_bull and (slope_v > 0.01)
    bear_aligned = h1_bear and h4_bear and (slope_v < -0.01)
    if (chop_v < 46.5) and (bull_aligned or bear_aligned) and (atr_ratio >= 0.80):
        return "SWEET", {
            "bull_trend": bull_aligned,
            "bear_trend": bear_aligned,
            "slope": slope_v,
            "accel": accel_v
        }

    # 4. รสเค็ม (SALTY): Adaptive CHOP สูง (>= 50.0 = ตลาดไซด์เวย์ในกรอบวัฏจักร) และราคาฉีกออกจาก KAMA
    if (chop_v >= 50.0) and (abs(prev_z) >= 1.50):
        return "SALTY", {
            "prev_z": prev_z,
            "p_accel": p_accel
        }

    return "BITTER", {"reason": "TRANSITION_ZONE"}
