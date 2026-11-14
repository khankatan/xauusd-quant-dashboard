from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนกลาง:
    รับรสชาติจากลิ้น (taste_market_flavor) แล้วประเมินว่ามีจุดเข้าที่ได้เปรียบจริงหรือไม่
    หากยังไม่ใช่จังหวะที่คมชัด จะส่งคืน (None, "") เพื่อให้นั่งรอ
    """
    t_mins = int(bar["thai_mins"])
    if not ((9 * 60 + 30) <= t_mins <= (21 * 60 + 45)):
        return None, ""

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    vwrsi_v = float(bar["vwrsi"])
    prev_rsi = float(prev["vwrsi"])
    fast_z = float(bar.get("fast_z", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    # 1. ให้ลิ้นชิมรสชาติของแท่งเทียนปัจจุบัน
    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars)

    if flavor == "BITTER":
        return None, ""

    # 2A. สมองส่วนรสหวาน (SWEET -> ย่อตัวตามเทรนด์ใหญ่ ไม่ไล่ราคาปลายแท่ง)
    if flavor == "SWEET":
        # ท่าที่ 1: ราคาย่อลงมาแตะเส้น VWAP แล้วดีดกลับตามเทรนด์
        if info["bull_trend"] and (prev["low"] <= prev["vwap"]) and (close_p > vwap_p) and (close_p > open_p):
            if (50 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (fast_z < 1.20):
                return "BUY", "SWEET-VWAP"

        if info["bear_trend"] and (prev["high"] >= prev["vwap"]) and (close_p < vwap_p) and (close_p < open_p):
            if (32 <= vwrsi_v <= 50) and (vwrsi_v < prev_rsi) and (fast_z > -1.20):
                return "SELL", "SWEET-VWAP"

        # ท่าที่ 2: พักตัว 1 แท่ง (Pullback Candle) แล้วส่งแรงไปต่อตามเทรนด์ (ไม่เข้าถ้าราคาฉีกไกลเกิน fast_z +-1.2)
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])
        if info["bull_trend"] and prev_red and (close_p > open_p) and (close_p > vwap_p) and (52 <= vwrsi_v <= 66) and (fast_z < 1.10):
            return "BUY", "SWEET-PB"
        if info["bear_trend"] and prev_green and (close_p < open_p) and (close_p < vwap_p) and (34 <= vwrsi_v <= 48) and (fast_z > -1.10):
            return "SELL", "SWEET-PB"

    # 2B. สมองส่วนรสเปรี้ยว (SOUR -> ดักสวนเมื่อเจ้ามือเพิ่งกวาด SL กรอบเอเชียเสร็จ)
    if flavor == "SOUR":
        if info["swept_low"] and (close_p > open_p) and (vwrsi_v > prev_rsi) and (30 <= vwrsi_v <= 55):
            if not (h1_bear and h4_bear):
                return "BUY", "SOUR-TRAP"

        if info["swept_high"] and (close_p < open_p) and (vwrsi_v < prev_rsi) and (45 <= vwrsi_v <= 70):
            if not (h1_bull and h4_bull):
                return "SELL", "SOUR-TRAP"

    # 2C. สมองส่วนรสเค็ม (SALTY -> ดักเด้งกลับเข้าหาค่าเฉลี่ยในสภาวะไซด์เวย์)
    if flavor == "SALTY":
        if (info["prev_z"] <= -1.60) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 46):
            if not (h1_bear and h4_bear):
                return "BUY", "SALTY-MR"

        if (info["prev_z"] >= 1.60) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 54):
            if not (h1_bull and h4_bull):
                return "SELL", "SALTY-MR"

    return None, ""
