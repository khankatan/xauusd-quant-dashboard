def evaluate_gap_filler(bar, prev, trades_today=0):
    """
    สมองซีกขวา (Right-Brain Intraday Daily Closer - V16.2 Regime-Adaptive):
    - ทำงานเฉพาะวันที่สมองหลัก (Left-Brain Sniper) ยังไม่ออกไม้เลย (trades_today == 0)
    - ช่วงเวลา 16:00 - 17:30 UTC (23:00 - 00:30 น. ไทย):
      1) Crisis Volatility Guard (ATR > 11.5 เช่น มี.ค. 2026): ต้องมี +OI ยืนยันเท่านั้น
      2) Trend Regime (CHOP < 46.0 เช่น เม.ย./พ.ค./มิ.ย.): บังคับสอดคล้องโครงสร้างใหญ่ H4 + VWAP
      3) Range/Summer Regime (CHOP >= 46.0 เช่น ก.ค.): ใช้ H1 + VWAP จับรอบสวิงนิวยอร์ก
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
    atr_val = float(bar["atr"])
    chop_v = float(bar.get("chop", 50.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    bull_oi = bool(bar.get("macro_bull_conv", False))
    bear_oi = bool(bar.get("macro_bear_conv", False))

    # 1. Crisis Volatility Guard (ATR > 11.5): บังคับต้องมี +OI ยืนยันเท่านั้น
    if atr_val > 11.5:
        if bull_oi and h1_bull and (close_p > open_p):
            return "BUY", "GAP-DAILY"
        if bear_oi and h1_bear and (close_p < open_p):
            return "SELL", "GAP-DAILY"
        return None, ""

    # 2. Trend Regime (CHOP < 46.0): บังคับสอดคล้อง H4 + VWAP ป้องกันการสวนเทรนด์ใหญ่ช่วงปลายวัน
    if chop_v < 46.0:
        if h1_bull and h4_bull and (close_p >= vwap_p) and (close_p > open_p) and (vwrsi_v >= 45):
            return "BUY", "GAP-DAILY"
        if h1_bear and h4_bear and (close_p <= vwap_p) and (close_p < open_p) and (vwrsi_v <= 55):
            return "SELL", "GAP-DAILY"
        return None, ""

    # 3. Sideways / Range Regime (CHOP >= 46.0): ใช้ H1 + VWAP จับรอบสวิงนิวยอร์ก
    if h1_bull and (close_p >= vwap_p) and (close_p > open_p) and (vwrsi_v >= 45):
        return "BUY", "GAP-DAILY"
    if h1_bear and (close_p <= vwap_p) and (close_p < open_p) and (vwrsi_v <= 55):
        return "SELL", "GAP-DAILY"

    return None, ""
