from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars, trades_today=0, day_open=None):
    t_mins = int(bar["thai_mins"])
    utc_hour = int(bar["thai_hour"]) - 7
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
    prev_kijun = float(prev.get("kijun", prev["close"]))

    vwrsi_v = float(bar["vwrsi"])
    prev_rsi = float(prev["vwrsi"])
    fast_z = float(bar.get("fast_z", 0.0))
    p_accel = float(bar.get("price_accel", 0.0))
    atr_val = float(bar["atr"])

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars, trades_today)

    if flavor == "BITTER":
        return None, ""

    has_oi = bool(info.get("has_macro_expansion", False))
    is_dead_zone_utc = (5 <= utc_hour <= 7) or (utc_hour == 12)
    is_crisis_vol = (atr_val > 11.5)
    chop_v = float(info.get("chop", 50.0))

    # 1. โหมดรสหวาน (SWEET)
    if flavor == "SWEET":
        # บล็อกชั่วโมง Pre-London / London Open Trap (06:00-07:59 UTC / 13:00-14:59 TH) เด็ดขาดแม้มี +OI (Win Rate 0%)
        if utc_hour in [6, 8]:
            return None, ""
        if is_dead_zone_utc and not has_oi:
            return None, ""

        k_slope = float(info.get("kama_slope", 0.0))
        atr_r = float(info.get("atr_ratio", 1.0))
        tk_bull = bool(info.get("tk_bull", False))
        tk_bear = bool(info.get("tk_bear", False))

        pulled_bull_vwap = (float(prev["low"]) <= float(prev["vwap"])) and (close_p > vwap_p)
        pulled_bear_vwap = (float(prev["high"]) >= float(prev["vwap"])) and (close_p < vwap_p)

        pulled_bull_tk = (t_mins <= 20 * 60 + 30) and tk_bull and (float(prev["low"]) <= prev_kijun) and (close_p > kijun_p) and (close_p > tenkan_p) and (close_p > vwap_p)
        pulled_bear_tk = (t_mins <= 20 * 60 + 30) and tk_bear and (float(prev["high"]) >= prev_kijun) and (close_p < kijun_p) and (close_p < tenkan_p) and (close_p < vwap_p)

        if chop_v < 50.0:
            left_bull_exp = ((chop_v < 38.2) and (k_slope > 0.01)) or ((atr_r >= 0.90) and (k_slope >= 0.03))
            left_bear_exp = ((chop_v < 38.2) and (k_slope < -0.01)) or ((atr_r >= 0.90) and (k_slope <= -0.03))

            if info["bull_trend"] and left_bull_exp and (close_p > open_p) and (52 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (fast_z <= 1.05):
                if pulled_bull_vwap:
                    return "BUY", "SWEET-VWAP"
                if pulled_bull_tk:
                    return "BUY", "SWEET-TK"

            if info["bear_trend"] and left_bear_exp and (close_p < open_p) and (32 <= vwrsi_v <= 48) and (vwrsi_v < prev_rsi) and (fast_z >= -1.05):
                if pulled_bear_vwap:
                    return "SELL", "SWEET-VWAP"
                if pulled_bear_tk:
                    return "SELL", "SWEET-TK"

        right_bull_flow = (k_slope > 0.0) and (has_oi or (chop_v < 46.5 and atr_r >= 0.72))
        right_bear_flow = (k_slope < 0.0) and (has_oi or (chop_v < 46.5 and atr_r >= 0.72))

        if info["bull_trend"] and right_bull_flow and (close_p > kama_p) and (close_p > open_p):
            if (50 <= vwrsi_v <= 68) and (vwrsi_v > prev_rsi) and (p_accel > 0.0) and (fast_z <= 1.00):
                if pulled_bull_vwap:
                    return "BUY", "SWEET-VWAP"
                if pulled_bull_tk:
                    return "BUY", "SWEET-TK"

        if info["bear_trend"] and right_bear_flow and (close_p < kama_p) and (close_p < open_p):
            if (32 <= vwrsi_v <= 50) and (vwrsi_v < prev_rsi) and (p_accel < 0.0) and (fast_z >= -1.00):
                if pulled_bear_vwap:
                    return "SELL", "SWEET-VWAP"
                if pulled_bear_tk:
                    return "SELL", "SWEET-TK"

    # 2. โหมดรสเปรี้ยว (SOUR): ป้องกันการดักสวน Super-Trend (CHOP < 40.5) หรือวันที่วิ่งมาแล้วเกิน 5.5 ATR
    if flavor == "SOUR":
        move_open = abs(close_p - day_open) / atr_val if (day_open is not None and atr_val > 0) else 0.0
        if (chop_v >= 40.5) and (move_open <= 5.5) and ((not is_crisis_vol) or has_oi):
            hemi = info.get("hemisphere", "L")
            if hemi == "L":
                if info["swept_low"] and h4_bull and (close_p > open_p) and (vwrsi_v > prev_rsi) and (30 <= vwrsi_v <= 52):
                    return "BUY", "SOUR-TRAP"
                if info["swept_high"] and h4_bear and (close_p < open_p) and (vwrsi_v < prev_rsi) and (48 <= vwrsi_v <= 70):
                    return "SELL", "SOUR-TRAP"
            else:
                if info["swept_low"] and (h1_bull and h4_bull) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (32 <= vwrsi_v <= 52):
                    return "BUY", "SOUR-TRAP"
                if info["swept_high"] and h4_bear and (close_p < open_p) and (vwrsi_v < prev_rsi) and (48 <= vwrsi_v <= 68):
                    return "SELL", "SOUR-TRAP"

    # 3. โหมดรสเค็ม (SALTY)
    if flavor == "SALTY":
        if (not is_crisis_vol) and (utc_hour not in [6, 11]):
            if h4_bull and (info["prev_z"] <= -1.55) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 45):
                return "BUY", "SALTY-MR"
            if h4_bear and (info["prev_z"] >= 1.55) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 55):
                return "SELL", "SALTY-MR"

    return None, ""
