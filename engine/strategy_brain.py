from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนกลาง V10 (Sensory-Driven Brain):
    1. ส่งข้อมูลแท่งเทียนให้ 'ลิ้น' (taste_market_flavor) ชิมรสชาติของตลาดก่อน
    2. แยกสั่งการตามรสชาติที่ได้รับ (SWEET -> ตามเทรนด์ / SOUR -> สวนกับดัก / SALTY -> ดักเด้งกรอบ)
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

    # ขั้นตอนที่ 1: ลิ้นชิมรสชาติของตลาด ณ แท่งปัจจุบัน
    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars)

    # รสขม (BITTER): คายทิ้ง ไม่เทรด
    if flavor == "BITTER":
        return None, ""

    # =========================================================================
    # ขั้นตอนที่ 2A: ได้รสหวาน (SWEET) -> สมองเลือกท่าตามเทรนด์ (Trend Pullback)
    # =========================================================================
    if flavor == "SWEET":
        # ท่าที่ 1: ย่อทดสอบเส้น VWAP แล้วดีดไปต่อตามเทรนด์ใหญ่
        if info["bull_trend"] and (prev["low"] <= prev["vwap"]) and (close_p > vwap_p) and (close_p > open_p):
            if (50 <= vwrsi_v <= 70) and (vwrsi_v > prev_rsi):
                return "BUY", "SWEET-VWAP"

        if info["bear_trend"] and (prev["high"] >= prev["vwap"]) and (close_p < vwap_p) and (close_p < open_p):
            if (30 <= vwrsi_v <= 50) and (vwrsi_v < prev_rsi):
                return "SELL", "SWEET-VWAP"

        # ท่าที่ 2: พักตัว 1 แท่งแล้วไปต่อตามแรงส่ง (Momentum Continuation)
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])
        if info["bull_trend"] and prev_red and (close_p > open_p) and (close_p > vwap_p) and (52 <= vwrsi_v <= 68):
            return "BUY", "SWEET-MOM"
        if info["bear_trend"] and prev_green and (close_p < open_p) and (close_p < vwap_p) and (32 <= vwrsi_v <= 48):
            return "SELL", "SWEET-MOM"

    # =========================================================================
    # ขั้นตอนที่ 2B: ได้รสเปรี้ยว (SOUR) -> สมองเลือกท่าสวนกับดัก (Liquidity Trap)
    # =========================================================================
    if flavor == "SOUR":
        # กวาด Low หรือทุบสุดโต่งแล้วแท่งเขียวตบกลับ (ห้ามสวน H1+H4 ขาลงพร้อมกัน)
        if (info["swept_low"] or info["prev_z"] <= -1.85) and (close_p > open_p) and (vwrsi_v > prev_rsi):
            if not (h1_bear and h4_bear):
                return "BUY", "SOUR-TRAP"

        # กวาด High หรือดีดสุดโต่งแล้วแท่งแดงตบกลับ (ห้ามสวน H1+H4 ขาขึ้นพร้อมกัน)
        if (info["swept_high"] or info["prev_z"] >= 1.85) and (close_p < open_p) and (vwrsi_v < prev_rsi):
            if not (h1_bull and h4_bull):
                return "SELL", "SOUR-TRAP"

    # =========================================================================
    # ขั้นตอนที่ 2C: ได้รสเค็ม (SALTY) -> สมองเลือกท่าดักเด้งในกรอบ (Mean Reversion)
    # =========================================================================
    if flavor == "SALTY":
        if (info["prev_z"] <= -1.50) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 48):
            if not (h1_bear and h4_bear):
                return "BUY", "SALTY-MR"

        if (info["prev_z"] >= 1.50) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 52):
            if not (h1_bull and h4_bull):
                return "SELL", "SALTY-MR"

    return None, ""
