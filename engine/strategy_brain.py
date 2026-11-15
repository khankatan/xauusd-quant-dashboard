from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars, trades_today=0):
    t_mins = int(bar["thai_mins"])
    utc_hour = int(bar["thai_hour"]) - 7  # แปลงเวลาไทยเป็น UTC โดยประมาณ
    if utc_hour < 0:
        utc_hour += 24

    if not ((9 * 60 + 30) <= t_mins <= (21 * 60 + 45)):
        return None, ""

    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    kama_p = float(bar.get("kama", vwap_p))
    tenkan_p = float(bar.get("tenkan", close_p))
    kijun_p = float(bar.get("kijun", close_p))

    vwrsi_v = float(bar["vwrsi"])
    prev_rsi = float(prev["vwrsi"])
    p_accel = float(bar.get("price_accel", 0.0))

    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars, trades_today)

    if flavor == "BITTER":
        return None, ""

    # ตรวจสอบกฎข้อ 1: บล็อก SWEET-VWAP ที่ไม่มี +OI ในช่วงรอยต่อ (05:00-07:00 UTC และ 12:00-13:00 UTC)
    has_oi = bool(info.get("has_macro_expansion", False))
    is_dead_zone_utc = (5 <= utc_hour <= 7) or (utc_hour == 12)

    # ตรวจสอบกฎข้อ 3: NY Session Fallback Window (13:00 - 16:30 UTC เมื่อ trades_today == 0)
    is_fallback_window = (13 <= utc_hour <= 16) and (trades_today == 0)
    fallback_mult = 0.875 if is_fallback_window else 1.0  # ผ่อนปรนระยะดึงกลับลง 12.5%

    if flavor == "SWEET":
        if is_dead_zone_utc and not has_oi:
            return None, ""  # บล็อกทิ้งตามเงื่อนไข

        chop_v = float(info.get("chop", 50.0))
        k_slope = float(info.get("kama_slope", 0.0))
        atr_r = float(info.get("atr_ratio", 1.0)) * fallback_mult  # ใช้ตัวคูณผ่อนปรนในโหมด Fallback

        pulled_bull_vwap = (float(prev["low"]) <= float(prev["vwap"]) * (1.0 + (0.001 * (1 - fallback_mult)))) and (close_p > vwap_p)
        pulled_bear_vwap = (float(prev["high"]) >= float(prev["vwap"]) * (1.0 - (0.001 * (1 - fallback_mult)))) and (close_p < vwap_p)

        if info["bull_trend"] and pulled_bull_vwap and (52 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi):
            return "BUY", "SWEET-VWAP"
        if info["bear_trend"] and pulled_bear_vwap and (32 <= vwrsi_v <= 48) and (vwrsi_v < prev_rsi):
            return "SELL", "SWEET-VWAP"

    if flavor == "SOUR":
        if info["swept_low"] and (close_p > open_p) and (vwrsi_v > prev_rsi):
            return "BUY", "SOUR-TRAP"
        if info["swept_high"] and (close_p < open_p) and (vwrsi_v < prev_rsi):
            return "SELL", "SOUR-TRAP"

    if flavor == "SALTY":
        # ช่วงรอยต่อที่บล็อก SWEET สามารถสลับมาให้ SALTY-MR ดักกรอบแทนได้
        if info["prev_z"] <= -1.55 and (close_p > open_p) and (vwrsi_v > prev_rsi):
            return "BUY", "SALTY-MR"
        if info["prev_z"] >= 1.55 and (close_p < open_p) and (vwrsi_v < prev_rsi):
            return "SELL", "SALTY-MR"

    return None, ""
