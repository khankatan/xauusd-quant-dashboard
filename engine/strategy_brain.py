from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนกลาง V15 (Dual-Hemisphere Left + Right Brain Coordination):
    - ขั้นที่ 1 (สมองซีกซ้าย - Left Hemisphere): ใช้เกณฑ์คณิตศาสตร์เข้มงวดจากไฟล์ 41 (WR 53.62%)
    - ขั้นที่ 2 (สมองซีกขวา - Right Hemisphere): หากซีกซ้ายไม่พบสัญญาณ ซีกขวาจะตรวจจับ Contextual Trend Flow
      (เทรนด์ไหลลื่นที่มี +OI หรือความชัน KAMA หนุนหลัง และการย่อพักตัว 2 แท่ง) เพื่อให้ออกไม้ได้สม่ำเสมอทุกวัน
    """
    t_mins = int(bar["thai_mins"])
    if not ((9 * 60 + 30) <= t_mins <= (21 * 60 + 45)):
        return None, ""

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    kama_p = float(bar.get("kama", vwap_p))
    atr_v = float(bar["atr"])
    vwrsi_v = float(bar["vwrsi"])
    prev_rsi = float(prev["vwrsi"])
    fast_z = float(bar.get("fast_z", 0.0))
    prev_z = float(prev.get("fast_z", 0.0))
    p_accel = float(bar.get("price_accel", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars)

    if flavor == "BITTER":
        return None, ""

    # =========================================================================
    # 1. โหมดรสหวาน (SWEET): ประสานสมองซีกซ้าย (L-Sniper) และสมองซีกขวา (R-Flow)
    # =========================================================================
    if flavor == "SWEET":
        chop_v = float(info.get("chop", 50.0))
        k_slope = float(info.get("kama_slope", 0.0))
        atr_r = float(info.get("atr_ratio", 1.0))
        has_oi = bool(info.get("has_macro_expansion", False))

        # ---------------------------------------------------------------------
        # [ซีกซ้าย - Left Hemisphere]: เกณฑ์คณิตศาสตร์เข้มงวด (CHOP < 50 + แรงส่งสูง)
        # ---------------------------------------------------------------------
        if chop_v < 50.0:
            left_bull_exp = ((chop_v < 38.2) and (k_slope > 0.01)) or ((atr_r >= 0.90) and (k_slope >= 0.03))
            left_bear_exp = ((chop_v < 38.2) and (k_slope < -0.01)) or ((atr_r >= 0.90) and (k_slope <= -0.03))

            if info["bull_trend"] and left_bull_exp and (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p) and (close_p > open_p):
                if (52 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (fast_z <= 1.05):
                    return "BUY", "SWEET-VWAP"

            if info["bear_trend"] and left_bear_exp and (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p) and (close_p < open_p):
                if (32 <= vwrsi_v <= 48) and (vwrsi_v < prev_rsi) and (fast_z >= -1.05):
                    return "SELL", "SWEET-VWAP"

            # ซีกซ้ายท่าที่ 2: ย่อแตะเส้น KAMA ในฝั่งขาขึ้น (ชนะ 100% ในไฟล์ 40 และ 41)
            prev_red = float(prev["close"]) < float(prev["open"])
            prev_kama = float(prev.get("kama", prev["vwap"]))
            touched_kama_bull = float(prev["low"]) <= (prev_kama + 0.15 * atr_v)

            if info["bull_trend"] and left_bull_exp and prev_red and touched_kama_bull and (close_p > open_p) and (close_p > kama_p) and (close_p > vwap_p):
                if (p_accel >= 0.05) and (50 <= vwrsi_v <= 65) and (fast_z <= 0.85):
                    return "BUY", "SWEET-KAMA"

        # ---------------------------------------------------------------------
        # [ซีกขวา - Right Hemisphere]: ทำงานเมื่อซีกซ้ายไม่ได้ยิง!
        # อ่านบริบทการไหลของเทรนด์ (Contextual Flow: เมื่อมี +OI หนุน หรือความชัน KAMA สอดคล้องกับเทรนด์)
        # ---------------------------------------------------------------------
        right_bull_flow = (k_slope > 0.0) and (has_oi or (chop_v < 46.5 and atr_r >= 0.72))
        right_bear_flow = (k_slope < 0.0) and (has_oi or (chop_v < 46.5 and atr_r >= 0.72))

        if info["bull_trend"] and right_bull_flow and (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p) and (close_p > kama_p) and (close_p > open_p):
            if (50 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (p_accel > 0.0) and (fast_z <= 1.00):
                return "BUY", "SWEET-VWAP"

        if info["bear_trend"] and right_bear_flow and (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p) and (close_p < kama_p) and (close_p < open_p):
            if (32 <= vwrsi_v <= 50) and (vwrsi_v < prev_rsi) and (p_accel < 0.0) and (fast_z >= -1.00):
                return "SELL", "SWEET-VWAP"

        # ซีกขวาท่าที่ 2: ย่อพักตัวในกรอบเวลาคลื่นไหลลื่น (Contextual Pullback Continuation)
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])
        if info["bull_trend"] and right_bull_flow and prev_red and (prev_z <= 0.35) and (close_p > open_p) and (close_p > vwap_p) and (close_p > kama_p):
            if (p_accel >= 0.06) and (vwrsi_v > prev_rsi) and (52 <= vwrsi_v <= 66) and (fast_z <= 0.90):
                return "BUY", "SWEET-KAMA"

        if info["bear_trend"] and right_bear_flow and prev_green and (prev_z >= -0.35) and (close_p < open_p) and (close_p < vwap_p) and (close_p < kama_p):
            if (p_accel <= -0.06) and (vwrsi_v < prev_rsi) and (34 <= vwrsi_v <= 48) and (fast_z >= -0.90):
                return "SELL", "SWEET-KAMA"

    # =========================================================================
    # 2. โหมดรสเปรี้ยว (SOUR): ประสานสมองซีกซ้าย (L) และซีกขวา (R)
    # =========================================================================
    if flavor == "SOUR":
        hemi = info.get("hemisphere", "L")
        if hemi == "L":
            if info["swept_low"] and h4_bull and (close_p > open_p) and (vwrsi_v > prev_rsi) and (30 <= vwrsi_v <= 52):
                return "BUY", "SOUR-TRAP"
            if info["swept_high"] and h4_bear and (close_p < open_p) and (vwrsi_v < prev_rsi) and (48 <= vwrsi_v <= 70):
                return "SELL", "SOUR-TRAP"
        else:
            # ซีกขวา (Right-Brain SOUR): เก็บจังหวะกวาดกรอบเอเชียฝั่งตามเทรนด์ใหญ่ H4 (ชนะ 83.3% ในไฟล์ 36)
            if info["swept_low"] and (h1_bull and h4_bull) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (32 <= vwrsi_v <= 52):
                return "BUY", "SOUR-TRAP"
            if info["swept_high"] and h4_bear and (close_p < open_p) and (vwrsi_v < prev_rsi) and (48 <= vwrsi_v <= 68):
                return "SELL", "SOUR-TRAP"

    # =========================================================================
    # 3. โหมดรสเค็ม (SALTY): ดักเด้งไซด์เวย์ตามโครงสร้างใหญ่ H4
    # =========================================================================
    if flavor == "SALTY":
        if h4_bull and (info["prev_z"] <= -1.55) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 45):
            return "BUY", "SALTY-MR"

        if h4_bear and (info["prev_z"] >= 1.55) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 55):
            return "SELL", "SALTY-MR"

    return None, ""
