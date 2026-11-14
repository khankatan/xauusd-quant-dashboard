from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนกลาง V11 (Adaptive Neural Brain):
    ใช้ค่า Dynamic RSI Mean/Std และเส้น KAMA ที่ยืดหยุ่นตามสภาวะตลาดแทนตัวเลขคงที่
    """
    t_mins = int(bar["thai_mins"])
    if not ((9 * 60 + 30) <= t_mins <= (21 * 60 + 45)):
        return None, ""

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    kama_p = float(bar.get("kama", vwap_p))
    vwrsi_v = float(bar["vwrsi"])
    prev_rsi = float(prev["vwrsi"])
    rsi_mean = float(bar.get("rsi_mean", 50.0))
    rsi_std = float(bar.get("rsi_std", 10.0))
    fast_z = float(bar.get("fast_z", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    # 1. ลิ้นชิมรสชาติของตลาดด้วยเกณฑ์แบบ Dynamic
    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars)

    if flavor == "BITTER":
        return None, ""

    # 2A. รสหวาน (SWEET -> ย่อตัวหาเส้นสมดุล VWAP หรือ KAMA แล้วดีดกลับตามเทรนด์ใหญ่)
    if flavor == "SWEET":
        # กรอบ RSI ปรับตัวเองตามค่าเฉลี่ย rsi_mean และส่วนเบี่ยงเบนมาตรฐาน rsi_std ของช่วงนั้น
        bull_rsi_ok = (rsi_mean - 0.3 * rsi_std) <= vwrsi_v <= (rsi_mean + 1.4 * rsi_std)
        bear_rsi_ok = (rsi_mean - 1.4 * rsi_std) <= vwrsi_v <= (rsi_mean + 0.3 * rsi_std)

        touched_bull_val = (float(prev["low"]) <= float(prev["vwap"])) or (float(prev["low"]) <= float(prev.get("kama", prev["vwap"])))
        touched_bear_val = (float(prev["high"]) >= float(prev["vwap"])) or (float(prev["high"]) >= float(prev.get("kama", prev["vwap"])))

        if info["bull_trend"] and touched_bull_val and (close_p > open_p) and (close_p > kama_p):
            if bull_rsi_ok and (vwrsi_v > prev_rsi) and (fast_z < 1.15):
                return "BUY", "SWEET-TREND"

        if info["bear_trend"] and touched_bear_val and (close_p < open_p) and (close_p < kama_p):
            if bear_rsi_ok and (vwrsi_v < prev_rsi) and (fast_z > -1.15):
                return "SELL", "SWEET-TREND"

    # 2B. รสเปรี้ยว (SOUR -> ดักสวนเมื่อกวาดสภาพคล่องกรอบเอเชียเสร็จแล้วตบกลับ)
    if flavor == "SOUR":
        if info["swept_low"] and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= rsi_mean + 0.5 * rsi_std):
            if not (h1_bear and h4_bear):
                return "BUY", "SOUR-TRAP"

        if info["swept_high"] and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= rsi_mean - 0.5 * rsi_std):
            if not (h1_bull and h4_bull):
                return "SELL", "SOUR-TRAP"

    # 2C. รสเค็ม (SALTY -> ดักเด้งเมื่อราคาฉีกทะลุกรอบ Dynamic Z-Band ของช่วงนั้นแล้วหมดแรง)
    if flavor == "SALTY":
        if (info["prev_z"] <= info["z_dn"]) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= rsi_mean - 0.4 * rsi_std):
            if not (h1_bear and h4_bear):
                return "BUY", "SALTY-MR"

        if (info["prev_z"] >= info["z_up"]) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= rsi_mean + 0.4 * rsi_std):
            if not (h1_bull and h4_bull):
                return "SELL", "SALTY-MR"

    return None, ""
