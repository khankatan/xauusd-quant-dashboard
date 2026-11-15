from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนกลาง V14.5 (All-Positive Sub-Agent Synthesis):
    1. SOUR-TRAP (เกณฑ์เข้มงวดไฟล์ 39): +$2,026.87 (WR 64.71%)
    2. SALTY-MR (เกณฑ์เข้มงวดไฟล์ 39): +$1,092.75 (WR 58.82%)
    3. SWEET-VWAP (เกณฑ์เข้มงวดไฟล์ 39): +$557.28 (WR 50.00%)
    4. SWEET-KAMA (เกณฑ์ย่อแตะเส้น KAMA ไฟล์ 40): +$210.77 (WR 66.67%)
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
    p_accel = float(bar.get("price_accel", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars)

    if flavor == "BITTER":
        return None, ""

    # 1. รสหวาน (SWEET -> ใช้เกณฑ์ Expansion เข้มงวดของไฟล์ 39: atr_r >= 0.90 & |k_slope| >= 0.03)
    if flavor == "SWEET":
        chop_v = float(info.get("chop", 50.0))
        k_slope = float(info.get("kama_slope", 0.0))
        atr_r = float(info.get("atr_ratio", 1.0))

        math_bull_expansion = ((chop_v < 38.2) and (k_slope > 0.01)) or ((atr_r >= 0.90) and (k_slope >= 0.03))
        math_bear_expansion = ((chop_v < 38.2) and (k_slope < -0.01)) or ((atr_r >= 0.90) and (k_slope <= -0.03))

        # ท่าที่ 1A: SWEET-VWAP (ใช้เกณฑ์ RSI 52-68 / 32-48 ตามไฟล์ 39 เป๊ะ -> กำไร +$557.28)
        if info["bull_trend"] and math_bull_expansion and (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p) and (close_p > open_p):
            if (52 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (fast_z <= 1.05):
                return "BUY", "SWEET-VWAP"

        if info["bear_trend"] and math_bear_expansion and (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p) and (close_p < open_p):
            if (32 <= vwrsi_v <= 48) and (vwrsi_v < prev_rsi) and (fast_z >= -1.05):
                return "SELL", "SWEET-VWAP"

        # ท่าที่ 1B: SWEET-KAMA (จากไฟล์ 40 -> ชนะ 66.67% กำไร +$210.77)
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])
        prev_kama = float(prev.get("kama", prev["vwap"]))

        touched_kama_bull = float(prev["low"]) <= (prev_kama + 0.15 * atr_v)
        touched_kama_bear = float(prev["high"]) >= (prev_kama - 0.15 * atr_v)

        if info["bull_trend"] and math_bull_expansion and prev_red and touched_kama_bull and (close_p > open_p) and (close_p > kama_p) and (close_p > vwap_p):
            if (p_accel >= 0.05) and (50 <= vwrsi_v <= 65) and (fast_z <= 0.85):
                return "BUY", "SWEET-KAMA"

        if info["bear_trend"] and math_bear_expansion and prev_green and touched_kama_bear and (close_p < open_p) and (close_p < kama_p) and (close_p < vwap_p):
            if (p_accel <= -0.05) and (35 <= vwrsi_v <= 50) and (fast_z >= -0.85):
                return "SELL", "SWEET-KAMA"

    # 2. รสเปรี้ยว (SOUR -> เกณฑ์เข้มงวดไฟล์ 39: RSI 30-52 / 48-70 -> กำไร +$2,026.87)
    if flavor == "SOUR":
        if info["swept_low"] and h4_bull and (close_p > open_p) and (vwrsi_v > prev_rsi) and (30 <= vwrsi_v <= 52):
            return "BUY", "SOUR-TRAP"

        if info["swept_high"] and h4_bear and (close_p < open_p) and (vwrsi_v < prev_rsi) and (48 <= vwrsi_v <= 70):
            return "SELL", "SOUR-TRAP"

    # 3. รสเค็ม (SALTY -> เกณฑ์เข้มงวดไฟล์ 39: |prev_z| >= 1.55 & RSI <= 45 / >= 55 -> กำไร +$1,092.75)
    if flavor == "SALTY":
        if h4_bull and (info["prev_z"] <= -1.55) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 45):
            return "BUY", "SALTY-MR"

        if h4_bear and (info["prev_z"] >= 1.55) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 55):
            return "SELL", "SALTY-MR"

    return None, ""
