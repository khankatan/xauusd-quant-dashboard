from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars, trades_today=0):
    """
    สมองส่วนกลาง V15.2 (Dynamic Tenkan-Kijun Equilibrium Value Zone):
    - ใช้เส้น Dynamic Tenkan-sen และ Kijun-sen เป็นแนวรับ-แนวต้านไดนามิกช่วงรันเทรนด์
    - ป้องกันการไล่ราคาปลายคลื่นด้วย Kijun Disparity (|kijun_disp| <= 1.65 ATR)
    - แทนที่ SWEET-KAMA SELL (ที่เคยขาดทุนในไฟล์ 42) ด้วยท่า SWEET-TK (ย่อทดสอบโซนสมดุล Tenkan/Kijun แล้วดีดกลับตามเทรนด์)
    """
    t_mins = int(bar["thai_mins"])
    if not ((8 * 60 + 30) <= t_mins <= (22 * 60 + 30)):
        return None, ""

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    kama_p = float(bar.get("kama", vwap_p))
    tenkan_p = float(bar.get("tenkan", close_p))
    kijun_p = float(bar.get("kijun", close_p))
    kijun_disp = float(bar.get("kijun_disp", 0.0))

    prev_tenkan = float(prev.get("tenkan", prev["close"]))
    prev_kijun = float(prev.get("kijun", prev["close"]))

    atr_v = float(bar["atr"])
    vwrsi_v = float(bar["vwrsi"])
    prev_rsi = float(prev["vwrsi"])
    fast_z = float(bar.get("fast_z", 0.0))
    p_accel = float(bar.get("price_accel", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars, trades_today)

    if flavor == "BITTER":
        return None, ""

    # =========================================================================
    # 1. โหมดรสหวาน (SWEET): ผสาน VWAP Pullback + Dynamic Tenkan/Kijun Equilibrium Zone
    # =========================================================================
    if flavor == "SWEET":
        chop_v = float(info.get("chop", 50.0))
        k_slope = float(info.get("kama_slope", 0.0))
        atr_r = float(info.get("atr_ratio", 1.0))
        has_oi = bool(info.get("has_macro_expansion", False))
        need_daily = bool(info.get("need_daily_trade", False))
        tk_bull = bool(info.get("tk_bull", False))
        tk_bear = bool(info.get("tk_bear", False))

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

        # [ซีกขวา - Right Hemisphere]: Contextual Flow + Dynamic Tenkan/Kijun Value Zone
        right_bull_flow = (k_slope > 0.0) and (has_oi or (chop_v < 46.5 and atr_r >= 0.72) or (need_daily and atr_r >= 0.65))
        right_bear_flow = (k_slope < 0.0) and (has_oi or (chop_v < 46.5 and atr_r >= 0.72) or (need_daily and atr_r >= 0.65))

        if info["bull_trend"] and right_bull_flow and (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p) and (close_p > kama_p) and (close_p > open_p):
            if (50 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (p_accel > 0.0) and (fast_z <= 1.00):
                return "BUY", "SWEET-VWAP"

        if info["bear_trend"] and right_bear_flow and (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p) and (close_p < kama_p) and (close_p < open_p):
            if (32 <= vwrsi_v <= 50) and (vwrsi_v < prev_rsi) and (p_accel < 0.0) and (fast_z >= -1.00):
                return "SELL", "SWEET-VWAP"

        # ---------------------------------------------------------------------
        # [ท่าใหม่ Dynamic Ichimoku TK Pullback]:
        # ราคาย่อตัวลงมาทดสอบแนวรับ-แนวต้าน Dynamic Tenkan-sen / Kijun-sen (TK Value Pocket)
        # แต่ไม่หลุดโครงสร้าง Kijun และไม่ฉีกตัวไกลเกิน Kijun Disparity (|kijun_disp| <= 1.60)
        # ---------------------------------------------------------------------
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])

        # ขาขึ้น: Tenkan >= Kijun, แท่งก่อนหน้าย่อลงมาแตะโซนแนวรับ Tenkan (แต่ไม่หลุด Kijun เกิน 0.2 ATR)
        # แล้วแท่งปัจจุบันดีดกลับปิดเขียวเหนือทั้ง Tenkan, KAMA และ VWAP พร้อมความเร่ง p_accel > 0
        pulled_to_tk_bull = (float(prev["low"]) <= prev_tenkan + 0.10 * atr_v) and (float(prev["close"]) >= prev_kijun - 0.15 * atr_v)
        if info["bull_trend"] and tk_bull and right_bull_flow and prev_red and pulled_to_tk_bull:
            if (close_p > open_p) and (close_p > tenkan_p) and (close_p > vwap_p) and (0.0 < kijun_disp <= 1.60):
                if (p_accel >= 0.05) and (vwrsi_v > prev_rsi) and (50 <= vwrsi_v <= 66) and (fast_z <= 0.90):
                    return "BUY", "SWEET-KAMA"

        # ขาลง: Tenkan <= Kijun, แท่งก่อนหน้าดีดขึ้นไปทดสอบแนวต้าน Tenkan (แต่ไม่ทะลุ Kijun เกิน 0.2 ATR)
        # แล้วแท่งปัจจุบันโดนตบกลับปิดแดงใต้ทั้ง Tenkan, KAMA และ VWAP พร้อมความเร่งทุบลง p_accel <= -0.07
        pulled_to_tk_bear = (float(prev["high"]) >= prev_tenkan - 0.10 * atr_v) and (float(prev["close"]) <= prev_kijun + 0.15 * atr_v)
        if info["bear_trend"] and tk_bear and right_bear_flow and prev_green and pulled_to_tk_bear:
            if (close_p < open_p) and (close_p < tenkan_p) and (close_p < vwap_p) and (-1.60 <= kijun_disp < 0.0):
                if (p_accel <= -0.07) and (vwrsi_v < prev_rsi) and (34 <= vwrsi_v <= 50) and (fast_z >= -0.90):
                    return "SELL", "SWEET-KAMA"

    # =========================================================================
    # 2. โหมดรสเปรี้ยว (SOUR): แชมป์ทำกำไร +$3,809.24 ในไฟล์ 42
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
            if (h1_bull and h4_bull) and (info["prev_z"] <= -1.28) and (p_accel >= 0.04) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 46):
                return "BUY", "SALTY-MR"
            if (h1_bear and h4_bear) and (info["prev_z"] >= 1.28) and (p_accel <= -0.04) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 54):
                return "SELL", "SALTY-MR"

    return None, ""
