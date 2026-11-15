from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars, trades_today=0):
    """
    สมองส่วนกลาง V15.3 (Pure Profitable Engines from File 42 + Dynamic Tenkan/Kijun Pullback):
    - ล็อกเวลาสแกนที่พิสูจน์แล้วว่าเสถียรที่สุด 09:30 - 21:45 น. (ไม่โดนหลอกช่วง 08:30-09:15 น. ที่ VWAP เพิ่งรีเซ็ต)
    - ถอด SWEET-KAMA (ตัวการเดียวที่ทำให้ไฟล์ 42, 43, 44 ขาดทุนไป -$932 ถึง -$2,410) ออกอย่างเด็ดขาด!
    - ใช้เส้น Dynamic Tenkan-sen และ Kijun-sen เป็นแนวรับ-แนวต้านเสริมให้กับ SWEET-VWAP:
      กล่าวคือ ถ้าราคาในเทรนด์ย่อลงมาแตะ Session VWAP หรือย่อลงมาแตะ Dynamic Tenkan/Kijun แล้วดีดกลับตามเทรนด์
      จะสามารถเปิดไม้ SWEET-VWAP ได้ทันที (ช่วยให้จับจังหวะย่อในเทรนด์ได้ครบขึ้นโดยไม่เกิดสัญญาณหลอก)
    """
    t_mins = int(bar["thai_mins"])
    if not ((9 * 60 + 30) <= t_mins <= (21 * 60 + 45)):
        return None, ""

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    kama_p = float(bar.get("kama", vwap_p))
    tenkan_p = float(bar.get("tenkan", close_p))
    kijun_p = float(bar.get("kijun", close_p))
    prev_tenkan = float(prev.get("tenkan", prev["close"]))
    prev_kijun = float(prev.get("kijun", prev["close"]))

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
    # 1. โหมดรสหวาน (SWEET): ประสานสมองซีกซ้าย + ซีกขวา พร้อมแนวรับ-แนวต้าน Dynamic Tenkan/Kijun
    # =========================================================================
    if flavor == "SWEET":
        chop_v = float(info.get("chop", 50.0))
        k_slope = float(info.get("kama_slope", 0.0))
        atr_r = float(info.get("atr_ratio", 1.0))
        has_oi = bool(info.get("has_macro_expansion", False))
        tk_bull = bool(info.get("tk_bull", False))
        tk_bear = bool(info.get("tk_bear", False))

        # แนวรับ-แนวต้านร่วมระหว่าง Session VWAP และ Dynamic Kijun-sen (เมื่อ Tenkan/Kijun เรียงตัวตามเทรนด์)
        pulled_bull_vwap = (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p)
        pulled_bull_tk = tk_bull and (float(prev["low"]) <= prev_kijun) and (close_p > kijun_p) and (close_p > tenkan_p) and (close_p > vwap_p)

        pulled_bear_vwap = (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p)
        pulled_bear_tk = tk_bear and (float(prev["high"]) >= prev_kijun) and (close_p < kijun_p) and (close_p < tenkan_p) and (close_p < vwap_p)

        # [ซีกซ้าย - Left Hemisphere]: เกณฑ์ Sniper เข้มงวด
        if chop_v < 50.0:
            left_bull_exp = ((chop_v < 38.2) and (k_slope > 0.01)) or ((atr_r >= 0.90) and (k_slope >= 0.03))
            left_bear_exp = ((chop_v < 38.2) and (k_slope < -0.01)) or ((atr_r >= 0.90) and (k_slope <= -0.03))

            if info["bull_trend"] and left_bull_exp and (pulled_bull_vwap or pulled_bull_tk) and (close_p > open_p):
                if (52 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (fast_z <= 1.05):
                    return "BUY", "SWEET-VWAP"

            if info["bear_trend"] and left_bear_exp and (pulled_bear_vwap or pulled_bear_tk) and (close_p < open_p):
                if (32 <= vwrsi_v <= 48) and (vwrsi_v < prev_rsi) and (fast_z >= -1.05):
                    return "SELL", "SWEET-VWAP"

        # [ซีกขวา - Right Hemisphere]: Contextual Flow (จากไฟล์ 42 ที่ทำกำไร +$960.83)
        right_bull_flow = (k_slope > 0.0) and (has_oi or (chop_v < 46.5 and atr_r >= 0.72))
        right_bear_flow = (k_slope < 0.0) and (has_oi or (chop_v < 46.5 and atr_r >= 0.72))

        if info["bull_trend"] and right_bull_flow and (pulled_bull_vwap or pulled_bull_tk) and (close_p > kama_p) and (close_p > open_p):
            if (50 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (p_accel > 0.0) and (fast_z <= 1.00):
                return "BUY", "SWEET-VWAP"

        if info["bear_trend"] and right_bear_flow and (pulled_bear_vwap or pulled_bear_tk) and (close_p < kama_p) and (close_p < open_p):
            if (32 <= vwrsi_v <= 50) and (vwrsi_v < prev_rsi) and (p_accel < 0.0) and (fast_z >= -1.00):
                return "SELL", "SWEET-VWAP"

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
    # 3. โหมดรสเค็ม (SALTY): ดักเด้งไซด์เวย์ตามโครงสร้างใหญ่ H4 (+$762.89 ในไฟล์ 42)
    # =========================================================================
    if flavor == "SALTY":
        if h4_bull and (info["prev_z"] <= -1.55) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 45):
            return "BUY", "SALTY-MR"

        if h4_bear and (info["prev_z"] >= 1.55) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 55):
            return "SELL", "SALTY-MR"

    return None, ""
