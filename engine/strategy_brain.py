def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    t_mins = int(bar["thai_mins"])
    close_p = float(bar["close"])
    open_p = float(bar["open"])
    vwap_p = float(bar["vwap"])
    vwrsi_v = float(bar["vwrsi"])

    # เปิดเทรดถึง 21:45 น. เวลาไทย ทั้งไม้หลักและไม้ต่อยอด (-H2, -H3) เพื่อรับ NY Session Volume
    if not ((9 * 60 + 30) <= t_mins <= (21 * 60 + 45)):
        return None, ""

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    # Agent 1: Exact Session VWAP Pullback
    if h1_bull and (prev["low"] <= prev["vwap"]) and (close_p > vwap_p) and (close_p > open_p):
        min_rsi = 50 if h4_bull else 54
        if (min_rsi <= vwrsi_v <= 70) and (vwrsi_v > prev["vwrsi"]):
            return "BUY", "VWAP-PB"

    if h1_bear and (prev["high"] >= prev["vwap"]) and (close_p < vwap_p) and (close_p < open_p):
        max_rsi = 50 if h4_bear else 46
        if (30 <= vwrsi_v <= max_rsi) and (vwrsi_v < prev["vwrsi"]):
            return "SELL", "VWAP-PB"

    # Agent 2: Evening Pullback to Value (18:15 - 21:45 น. รับ NY Volume เต็มช่วง)
    if (18 * 60 + 15) <= t_mins <= (21 * 60 + 45):
        prev_red = float(prev["close"]) < float(prev["open"])
        prev_green = float(prev["close"]) > float(prev["open"])
        if h1_bull and h4_bull and prev_red and (close_p > open_p) and (close_p > vwap_p) and (52 <= vwrsi_v <= 68):
            return "BUY", "EV-PB"
        if h1_bear and h4_bear and prev_green and (close_p < open_p) and (close_p < vwap_p) and (32 <= vwrsi_v <= 48):
            return "SELL", "EV-PB"

    return None, ""
