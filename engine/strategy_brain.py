from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนกลาง V13.1:
    - SWEET-VWAP: ทำงานเฉพาะช่วง Expansion Window (09:30-09:59, 15:00-16:45, 20:00-21:45 น.)
      หรือเมื่อค่า CHOP < 38.2 (Fibonacci Pure Trend) เท่านั้น! (ตัดขาดทุน -$7,655 ในช่วงตลาดซึม)
    - SWEET-EV: ทำงานช่วง 18:15 - 21:45 น. (ชนะ 75% ในช่วงหัวค่ำ)
    - SALTY-MR: ดักเด้งเมื่อราคาฉีกออกนอกกรอบ (ชนะ 64.3% - 64.7% ในไฟล์ 33 และ 34)
    - SOUR-TRAP: ดักสวนกับดักกวาดขอบ Asian Box
    """
    t_mins = int(bar["thai_mins"])
    t_hour = int(bar["thai_hour"])
    if not ((9 * 60 + 30) <= t_mins <= (21 * 60 + 45)):
        return None, ""

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    vwrsi_v = float(bar["vwrsi"])
    prev_rsi = float(prev["vwrsi"])

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars)

    if flavor == "BITTER":
        return None, ""

    # 1. รสหวาน (SWEET -> แยกเงื่อนไข SWEET-VWAP และ SWEET-EV ตามสถิติจริง)
    if flavor == "SWEET":
        # SWEET-VWAP: อนุญาตเฉพาะชั่วโมง Expansion (09, 15, 16, 20, 21) หรือเมื่อเกิดเทรนด์บริสุทธิ์ CHOP < 38.2 เท่านั้น
        in_vwap_expansion_hour = t_hour in (9, 15, 16, 20, 21)
        is_pure_fib_trend = float(info.get("chop", 50.0)) < 38.2

        if in_vwap_expansion_hour or is_pure_fib_trend:
            if info["bull_trend"] and (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p) and (close_p > open_p):
                if (50 <= vwrsi_v <= 70) and (vwrsi_v > prev_rsi):
                    return "BUY", "SWEET-VWAP"

            if info["bear_trend"] and (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p) and (close_p < open_p):
                if (30 <= vwrsi_v <= 50) and (vwrsi_v < prev_rsi):
                    return "SELL", "SWEET-VWAP"

        # SWEET-EV: ย่อพักตัว 1 แท่งในรอบค่ำ (18:15 - 21:45 น.)
        if (18 * 60 + 15) <= t_mins <= (21 * 60 + 45):
            prev_red = float(prev["close"]) < float(prev["open"])
            prev_green = float(prev["close"]) > float(prev["open"])
            if info["bull_trend"] and prev_red and (close_p > open_p) and (close_p > vwap_p) and (52 <= vwrsi_v <= 68):
                return "BUY", "SWEET-EV"
            if info["bear_trend"] and prev_green and (close_p < open_p) and (close_p < vwap_p) and (32 <= vwrsi_v <= 48):
                return "SELL", "SWEET-EV"

    # 2. รสเปรี้ยว (SOUR -> ดักสวนกับดักกวาดกรอบเอเชีย)
    if flavor == "SOUR":
        if info["swept_low"] and (close_p > open_p) and (vwrsi_v > prev_rsi) and (30 <= vwrsi_v <= 55):
            if h4_bull:
                return "BUY", "SOUR-TRAP"

        if info["swept_high"] and (close_p < open_p) and (vwrsi_v < prev_rsi) and (45 <= vwrsi_v <= 70):
            if not (h1_bull and h4_bull):
                return "SELL", "SOUR-TRAP"

    # 3. รสเค็ม (SALTY -> ดักเด้งเมื่อราคาฉีกออกนอกกรอบ ชนะ 64.3%-64.7% ทั้งในไฟล์ 33 และ 34)
    if flavor == "SALTY":
        if (info["prev_z"] <= -1.50) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 46):
            if not (h1_bear and h4_bear):
                return "BUY", "SALTY-MR"

        if (info["prev_z"] >= 1.50) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 54):
            if not (h1_bull and h4_bull):
                return "SELL", "SALTY-MR"

    return None, ""
