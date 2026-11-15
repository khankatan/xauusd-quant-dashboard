from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนกลาง V13 (Preserving Proven Winners from Runs 25/26, 29, and 32):
    - SWEET: ใช้สูตร VWAP-PB และ EV-PB ดั้งเดิมจากไฟล์ 25/26 ที่ทำกำไรในเดือน ส.ค., ต.ค., พ.ย.
    - SALTY: ใช้สูตร SALTY-MR ดั้งเดิมจากไฟล์ 29 ที่ทำกำไรในเดือน พ.ค. (+$1,644), ส.ค. (+$3,508), ต.ค. (+$2,632)
    - SOUR: ใช้สูตร SOUR-TRAP จากไฟล์ 32 ที่ทำกำไร +$1,762
    """
    t_mins = int(bar["thai_mins"])
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

    # 1. รสหวาน (SWEET -> สูตร VWAP-PB และ EV-PB ดั้งเดิมจากไฟล์ 25/26)
    if flavor == "SWEET":
        # VWAP-PB: ย่อแตะ Session VWAP แล้วดีดกลับตามเทรนด์
        if info["bull_trend"] and (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p) and (close_p > open_p):
            if (50 <= vwrsi_v <= 70) and (vwrsi_v > prev_rsi):
                return "BUY", "SWEET-VWAP"

        if info["bear_trend"] and (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p) and (close_p < open_p):
            if (30 <= vwrsi_v <= 50) and (vwrsi_v < prev_rsi):
                return "SELL", "SWEET-VWAP"

        # EV-PB: ย่อพักตัว 1 แท่งในรอบค่ำ (18:15 - 21:45 น.) แล้วไปต่อตามเทรนด์
        if (18 * 60 + 15) <= t_mins <= (21 * 60 + 45):
            prev_red = float(prev["close"]) < float(prev["open"])
            prev_green = float(prev["close"]) > float(prev["open"])
            if info["bull_trend"] and prev_red and (close_p > open_p) and (close_p > vwap_p) and (52 <= vwrsi_v <= 68):
                return "BUY", "SWEET-EV"
            if info["bear_trend"] and prev_green and (close_p < open_p) and (close_p < vwap_p) and (32 <= vwrsi_v <= 48):
                return "SELL", "SWEET-EV"

    # 2. รสเปรี้ยว (SOUR -> สูตร SOUR-TRAP ที่ทำกำไร +$1,762 ในไฟล์ 32)
    if flavor == "SOUR":
        if info["swept_low"] and (close_p > open_p) and (vwrsi_v > prev_rsi) and (30 <= vwrsi_v <= 55):
            if not (h1_bear and h4_bear):
                return "BUY", "SOUR-TRAP"

        if info["swept_high"] and (close_p < open_p) and (vwrsi_v < prev_rsi) and (45 <= vwrsi_v <= 70):
            if not (h1_bull and h4_bull):
                return "SELL", "SOUR-TRAP"

    # 3. รสเค็ม (SALTY -> สูตร SALTY-MR ดั้งเดิมจากไฟล์ 29)
    if flavor == "SALTY":
        if (info["prev_z"] <= -1.60) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 46):
            if not (h1_bear and h4_bear):
                return "BUY", "SALTY-MR"

        if (info["prev_z"] >= 1.60) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 54):
            if not (h1_bull and h4_bull):
                return "SELL", "SALTY-MR"

    return None, ""
