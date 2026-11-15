def evaluate_gap_filler(bar, prev, trades_today=0):
    """
    สมองซีกขวา (Right-Brain Intraday Daily Closer - V16 Isolated Dual-Brain):
    - ทำงานเฉพาะวันที่สมองหลัก (Left-Brain Sniper) ยังไม่ออกไม้เลย (trades_today == 0)
    - ช่วงเวลา 16:00 - 17:30 UTC (23:00 - 00:30 น. ไทย): จับกระแสช่วงปลายตลาดนิวยอร์กหลังโครงสร้างชัดเจนแล้ว
    - ปิดจบภายในวันก่อน 02:30 น. ไทย เพื่อไม่ให้ขวางจังหวะเข้าของ SWEET-VWAP ในรอบเช้าวันถัดไป
    """
    if trades_today > 0:
        return None, ""

    utc_hour = int(bar["thai_hour"]) - 7
    if utc_hour < 0:
        utc_hour += 24

    utc_mins = utc_hour * 60 + int(bar["thai_minute"])
    if not ((16 * 60) <= utc_mins <= (17 * 60 + 30)):
        return None, ""

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    vwrsi_v = float(bar["vwrsi"])

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])

    if h1_bull and (close_p > open_p) and (vwrsi_v >= 45):
        return "BUY", "GAP-DAILY"
    if h1_bear and (close_p < open_p) and (vwrsi_v <= 55):
        return "SELL", "GAP-DAILY"
    if (close_p > vwap_p) and (close_p > open_p):
        return "BUY", "GAP-DAILY"
    if (close_p < vwap_p) and (close_p < open_p):
        return "SELL", "GAP-DAILY"

    return None, ""
