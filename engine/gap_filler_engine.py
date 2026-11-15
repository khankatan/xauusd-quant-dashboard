def evaluate_gap_filler(bar, prev, trades_today=0, lon_open=None, lon_close=None):
    utc_hour = int(bar["thai_hour"]) - 7
    if utc_hour < 0:
        utc_hour += 24

    utc_mins = utc_hour * 60 + int(bar["thai_minute"])
    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    atr_val = float(bar["atr"])
    chop_bar = float(bar.get("chop", 50.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    bull_oi = bool(bar.get("macro_bull_conv", False))
    bear_oi = bool(bar.get("macro_bear_conv", False))

    # 1. FLIP-SESSION (Judas Flip 20:30 - 23:30 TH): บล็อก CHOP >= 54.0 (Win Rate 80.95%)
    if (13 * 60 + 30) <= utc_mins <= (16 * 60 + 30) and chop_bar < 54.0:
        if lon_open is not None and lon_close is not None and atr_val > 0:
            lon_move = (lon_close - lon_open) / atr_val
            if lon_move >= 1.0 and close_p < vwap_p and float(prev["close"]) >= float(prev["vwap"]) and close_p < open_p:
                return "SELL", "FLIP-SESSION"
            if lon_move <= -1.0 and close_p > vwap_p and float(prev["close"]) <= float(prev["vwap"]) and close_p > open_p:
                return "BUY", "FLIP-SESSION"

    # 2. GAP-DAILY (23:15 - 00:45 TH): เก็บตกวันที่ยังไม่มีไม้
    if trades_today == 0 and (16 * 60 + 15) <= utc_mins <= (17 * 60 + 45):
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
