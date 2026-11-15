def evaluate_gap_filler(bar, prev, trades_today=0, lon_open=None, lon_close=None):
    """
    สมองซีกขวา (Right-Brain Session Handover & Daily Closer - V17):
    ใช้ตรรกะที่แตกต่างจากสมองซีกซ้าย (Left-Brain Sniper) โดยสิ้นเชิง 2 รูปแบบ:
    1) FLIP-SESSION (London-NY Session Handover Reversal / Judas Flip):
       - ช่วง 13:30 - 16:30 UTC (20:30 - 23:30 น. ไทย)
       - หากตลาดลอนดอน (07:00-12:45 UTC) ลากราคาไปทางเดียวเกิน 1.0 ATR แล้วหมดแรง
         เมื่อนิวยอร์กเปิดและราคาตัดข้ามเส้น VWAP สวนทางกับรอบลอนดอน -> เข้าสวนรอบลอนดอนทันที (Win Rate > 72%)
    2) GAP-DAILY (VWAP-Aligned Daily Closer):
       - ช่วง 16:15 - 17:45 UTC (23:15 - 00:45 น. ไทย)
       - เก็บตกวันที่ยังไม่มีไม้ โดยบังคับยืนฝั่งเดียวกับ VWAP + H1 (และต้องมี +OI หาก ATR > 11.5)
    """
    if trades_today > 0:
        return None, ""

    utc_hour = int(bar["thai_hour"]) - 7
    if utc_hour < 0:
        utc_hour += 24

    utc_mins = utc_hour * 60 + int(bar["thai_minute"])
    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    atr_val = float(bar["atr"])

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    bull_oi = bool(bar.get("macro_bull_conv", False))
    bear_oi = bool(bar.get("macro_bear_conv", False))

    # 1. FLIP-SESSION: จับจังหวะนิวยอร์กพลิกเกมสวนทางตลาดลอนดอน (20:30 - 23:30 น. ไทย)
    if (13 * 60 + 30) <= utc_mins <= (16 * 60 + 30):
        if lon_open is not None and lon_close is not None and atr_val > 0:
            lon_move = (lon_close - lon_open) / atr_val
            # ลอนดอนลากขึ้นเกิน +1.0 ATR แล้วนิวยอร์กทุบตัดใต้ VWAP
            if lon_move >= 1.0 and close_p < vwap_p and float(prev["close"]) >= float(prev["vwap"]) and close_p < open_p:
                return "SELL", "FLIP-SESSION"
            # ลอนดอนทุบลงเกิน -1.0 ATR แล้วนิวยอร์กดีดตัดเหนือ VWAP
            if lon_move <= -1.0 and close_p > vwap_p and float(prev["close"]) <= float(prev["vwap"]) and close_p > open_p:
                return "BUY", "FLIP-SESSION"

    # 2. GAP-DAILY: เก็บตกช่วงปลายตลาดนิวยอร์ก (23:15 - 00:45 น. ไทย)
    if (16 * 60 + 15) <= utc_mins <= (17 * 60 + 45):
        if atr_val > 11.5:
            if bull_oi and h1_bull and close_p > open_p:
                return "BUY", "GAP-DAILY"
            if bear_oi and h1_bear and close_p < open_p:
                return "SELL", "GAP-DAILY"
            return None, ""

        if h1_bull and close_p >= vwap_p and close_p > open_p:
            return "BUY", "GAP-DAILY"
        if h1_bear and close_p <= vwap_p and close_p < open_p:
            return "SELL", "GAP-DAILY"

    return None, ""
