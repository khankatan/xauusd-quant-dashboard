from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนกลาง V14.4:
    - คงสูตร SOUR-TRAP (+$2,026), SALTY-MR (+$1,092), และ SWEET-VWAP (+$557) ที่ทำกำไรชนะในไฟล์ 39 ไว้ครบ
    - ซ่อมจุดรั่วตัวเดียวของไฟล์ 39 (SWEET-EV -$2,159): บังคับให้แท่งก่อนหน้าต้อง 'ย่อลงมาแตะหรือใกล้เส้น KAMA' จริง
      ห้ามเข้าซื้อเมื่อแท่งเทียนลอยอยู่กลางอากาศห่างจากเส้นสมดุล
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

    # 1. รสหวาน (SWEET -> ต้องย่อแตะเส้น VWAP หรือเส้น KAMA จริง ไม่ไล่ราคาปลายคลื่น)
    if flavor == "SWEET":
        chop_v = float(info.get("chop", 50.0))
        k_slope = float(info.get("kama_slope", 0.0))
        atr_r = float(info.get("atr_ratio", 1.0))

        math_bull_expansion = ((chop_v < 38.2) and (k_slope > 0.01)) or ((atr_r >= 0.86) and (k_slope >= 0.025))
        math_bear_expansion = ((chop_v < 38.2) and (k_slope < -0.01)) or ((atr_r >= 0.86) and (k_slope <= -0.025))

        # ท่าที่ 1A: SWEET-VWAP (กำไร +$557.28 ในไฟล์ 39)
        if info["bull_trend"] and math_bull_expansion and (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p) and (close_p > open_p):
            if (50 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (fast_z <= 1.05):
                return "BUY", "SWEET-VWAP"

        if info["bear_trend"] and math_bear_expansion and (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p) and (close_p < open_p):
            if (32 <= vwrsi_v <= 50) and (vwrsi_v < prev_rsi) and (fast_z >= -1.05):
                return "SELL", "SWEET-VWAP"

        # ท่าที่ 1B: SWEET-KAMA (แทนที่ SWEET-EV เดิมที่ไล่ราคากลางอากาศ: บังคับให้แท่งก่อนหน้าย่อลงมาแตะเส้น KAMA จริง!)
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

    # 2. รสเปรี้ยว (SOUR -> ทำกำไรสูงสุด +$2,026.87 / WR 64.71% ในไฟล์ 39)
    if flavor == "SOUR":
        if info["swept_low"] and h4_bull and (close_p > open_p) and (vwrsi_v > prev_rsi) and (28 <= vwrsi_v <= 54):
            return "BUY", "SOUR-TRAP"

        if info["swept_high"] and h4_bear and (close_p < open_p) and (vwrsi_v < prev_rsi) and (46 <= vwrsi_v <= 72):
            return "SELL", "SOUR-TRAP"

    # 3. รสเค็ม (SALTY -> ทำกำไร +$1,092.75 / WR 58.82% ในไฟล์ 39)
    if flavor == "SALTY":
        if h4_bull and (info["prev_z"] <= -1.42) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 46):
            return "BUY", "SALTY-MR"

        if h4_bear and (info["prev_z"] >= 1.42) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 54):
            return "SELL", "SALTY-MR"

    return None, ""
