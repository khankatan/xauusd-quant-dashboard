from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars, trades_today=0):
    """
    สมองส่วนกลาง V15.1 (File 39 + File 42 Best-of-Both Synthesis):
    1. เก็บ SOUR-TRAP (+$3,809), SWEET-VWAP (+$961), SALTY-MR (+$763) และ SWEET-KAMA BUY (+$77) จากไฟล์ 42 ไว้ครบ
    2. ตัด SWEET-KAMA SELL (ที่แพ้ 8/9 ไม้ ขาดทุน -$2,487.10 ในไฟล์ 42) ทิ้งทันที!
    3. คืนชีพท่า SWEET-EV SELL จากไฟล์ 39/37 (ที่ชนะ 69.2% ในวันที่ไฟล์ 42 เงียบ) เฉพาะเมื่อมีแรงทุบแคลคูลัสคมชัด
    4. ขยายเวลาสแกนเป็น 08:30 - 22:30 น. และใช้สมองซีกขวาช่วยเติมไม้ในวันที่ยังไม่ได้เทรดหลัง 15:00 น.
    """
    t_mins = int(bar["thai_mins"])
    if not ((8 * 60 + 30) <= t_mins <= (22 * 60 + 30)):
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

    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars, trades_today)

    if flavor == "BITTER":
        return None, ""

    # =========================================================================
    # 1. โหมดรสหวาน (SWEET): ประสานสมองซีกซ้าย + ซีกขวา (ตัด SWEET-KAMA SELL ทิ้ง!)
    # =========================================================================
    if flavor == "SWEET":
        chop_v = float(info.get("chop", 50.0))
        k_slope = float(info.get("kama_slope", 0.0))
        atr_r = float(info.get("atr_ratio", 1.0))
        has_oi = bool(info.get("has_macro_expansion", False))
        need_daily = bool(info.get("need_daily_trade", False))

        # [ซีกซ้าย - Left Hemisphere]: เกณฑ์ Sniper เข้มงวด
        if chop_v < 50.0:
            left_bull_exp = ((chop_v < 38.2) and (k_slope > 0.01)) or ((atr_r >= 0.90) and (k_slope >= 0.03))
            left_bear_exp = ((chop_v < 38.2) and (k_slope < -0.01)) or ((atr_r >= 0.90) and (k_slope <= -0.03))

            if info["bull_trend"] and left_bull_exp and (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p) and (close_p > open_p):
                if (52 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (fast_z <= 1.05):
                    return "BUY", "SWEET-VWAP"

            if info["bear_trend"] and left_bear_exp and (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p) and (close_p < open_p):
                if (32 <= vwrsi_v <= 48) and (vwrsi_v < prev_rsi) and (fast_z >= -1.05):
                    return "SELL", "SWEET-VWAP"

            # SWEET-KAMA อนุญาตเฉพาะฝั่ง BUY เท่านั้น! (ตัดฝั่ง SELL ที่แพ้ 8/9 ไม้ -$2,487 ทิ้งเด็ดขาด)
            prev_red = float(prev["close"]) < float(prev["open"])
            prev_kama = float(prev.get("kama", prev["vwap"]))
            touched_kama_bull = float(prev["low"]) <= (prev_kama + 0.15 * atr_v)

            if info["bull_trend"] and left_bull_exp and prev_red and touched_kama_bull and (close_p > open_p) and (close_p > kama_p) and (close_p > vwap_p):
                if (p_accel >= 0.05) and (50 <= vwrsi_v <= 65) and (fast_z <= 0.85):
                    return "BUY", "SWEET-KAMA"

        # [ซีกขวา - Right Hemisphere]: Contextual Flow & Daily Quota Filler
        right_bull_flow = (k_slope > 0.0) and (has_oi or (chop_v < 46.5 and atr_r >= 0.72) or (need_daily and atr_r >= 0.65))
        right_bear_flow = (k_slope < 0.0) and (has_oi or (chop_v < 46.5 and atr_r >= 0.72) or (need_daily and atr_r >= 0.65))

        if info["bull_trend"] and right_bull_flow and (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p) and (close_p > kama_p) and (close_p > open_p):
            if (50 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (p_accel > 0.0) and (fast_z <= 1.00):
                return "BUY", "SWEET-VWAP"

        if info["bear_trend"] and right_bear_flow and (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p) and (close_p < kama_p) and (close_p < open_p):
            if (32 <= vwrsi_v <= 50) and (vwrsi_v < prev_rsi) and (p_accel < 0.0) and (fast_z >= -1.00):
                return "SELL", "SWEET-VWAP"

        # ซีกขวาขาขึ้น: SWEET-KAMA BUY (เฉพาะฝั่ง BUY)
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])
        if info["bull_trend"] and right_bull_flow and prev_red and (prev_z <= 0.35) and (close_p > open_p) and (close_p > vwap_p) and (close_p > kama_p):
            if (p_accel >= 0.06) and (vwrsi_v > prev_rsi) and (52 <= vwrsi_v <= 66) and (fast_z <= 0.90):
                return "BUY", "SWEET-KAMA"

        # ซีกขวาขาลง: คืนชีพ SWEET-EV SELL จากไฟล์ 39/37 (ที่ชนะ 69.2% ในวันที่ไฟล์ 42 เงียบ!)
        # เข้าเมื่อแท่งก่อนหน้าดีดเขียวพักตัว แต่ปิดใต้ VWAP/KAMA แล้วแท่งนี้เกิดแรงทุบแคลคูลัสส่งลงต่อ
        if info["bear_trend"] and right_bear_flow and prev_green and (close_p < open_p) and (close_p < vwap_p) and (close_p < kama_p):
            if (p_accel <= -0.08) and (vwrsi_v < prev_rsi) and (34 <= vwrsi_v <= 48) and (fast_z >= -0.95):
                return "SELL", "SWEET-EV"

    # =========================================================================
    # 2. โหมดรสเปรี้ยว (SOUR): แชมป์ทำกำไร +$3,809.24 (WR 67.74%) ในไฟล์ 42
    # =========================================================================
    if flavor == "SOUR":
        hemi = info.get("hemisphere", "L")
        if hemi == "L":
            if info["swept_low"] and h4_bull and (close_p > open_p) and (vwrsi_v > prev_rsi) and (30 <= vwrsi_v <= 52):
                return "BUY", "SOUR-TRAP"
            if info["swept_high"] and h4_bear and (close_p < open_p) and (vwrsi_v < prev_rsi) and (48 <= vwrsi_v <= 70):
                return "SELL", "SOUR-TRAP"
        else:
            if info["swept_low"] and (h1_bull and h4_bull) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (32 <= vwrsi_v <= 52):
                return "BUY", "SOUR-TRAP"
            if info["swept_high"] and h4_bear and (close_p < open_p) and (vwrsi_v < prev_rsi) and (48 <= vwrsi_v <= 68):
                return "SELL", "SOUR-TRAP"

    # =========================================================================
    # 3. โหมดรสเค็ม (SALTY): ซีกซ้าย (|z| >= 1.55) + ซีกขวาช่วยเติมไม้รายวัน (|z| >= 1.28)
    # =========================================================================
    if flavor == "SALTY":
        hemi = info.get("hemisphere", "L")
        if hemi == "L":
            if h4_bull and (info["prev_z"] <= -1.55) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 45):
                return "BUY", "SALTY-MR"
            if h4_bear and (info["prev_z"] >= 1.55) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 55):
                return "SELL", "SALTY-MR"
        else:
            # ซีกขวา (Daily Filler หลัง 15:00 น. เมื่อวันนี้ยังไม่มีไม้): ต้องมีความเร่ง p_accel ยืนยันการเด้งกลับ
            if (h1_bull and h4_bull) and (info["prev_z"] <= -1.28) and (p_accel >= 0.04) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 46):
                return "BUY", "SALTY-MR"
            if (h1_bear and h4_bear) and (info["prev_z"] >= 1.28) and (p_accel <= -0.04) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 54):
                return "SELL", "SALTY-MR"

    return None, ""
