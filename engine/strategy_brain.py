from engine.taste_buds import taste_market_flavor

def evaluate_signals(bar, prev, asian_high, asian_low, asian_bars):
    """
    สมองส่วนกลาง V12 (Hilbert Cycle + CHOP + Calculus Derivative Confirmation):
    ตรวจสอบอนุพันธ์อันดับ 1 (Slope) และอนุพันธ์อันดับ 2 (Acceleration) เพื่อยืนยันว่าแรงซื้อ/ขายยังไม่หมด
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
    fast_z = float(bar.get("fast_z", 0.0))
    accel_v = float(bar.get("accel", 0.0))
    p_accel = float(bar.get("price_accel", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])

    flavor, info = taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars)

    if flavor == "BITTER":
        return None, ""

    # 1. โหมดรสหวาน (SWEET -> ย่อแตะเส้น KAMA หรือ VWAP แล้วเกิดความเร่งส่งตัวกลับตามเทรนด์)
    if flavor == "SWEET":
        pulled_to_bull_zone = (float(prev["low"]) <= float(prev["kama"])) or (float(prev["low"]) <= float(prev["vwap"]))
        pulled_to_bear_zone = (float(prev["high"]) >= float(prev["kama"])) or (float(prev["high"]) >= float(prev["vwap"]))

        # ยืนยันด้วยแคลคูลัส: ความเร่งของราคา (p_accel > 0) หรือความเร่ง KAMA (accel_v >= -0.02) ต้องไม่หัวทิ่มลง
        if info["bull_trend"] and pulled_to_bull_zone and (close_p > open_p) and (close_p > kama_p):
            if (p_accel > 0.0) and (accel_v >= -0.02) and (48 <= vwrsi_v <= 68) and (fast_z < 1.15):
                return "BUY", "SWEET-TREND"

        if info["bear_trend"] and pulled_to_bear_zone and (close_p < open_p) and (close_p < kama_p):
            if (p_accel < 0.0) and (accel_v <= 0.02) and (32 <= vwrsi_v <= 52) and (fast_z > -1.15):
                return "SELL", "SWEET-TREND"

    # 2. โหมดรสเปรี้ยว (SOUR -> กวาดสภาพคล่องกรอบเอเชียแล้วความเร่งดีดกลับเข้ากรอบ)
    if flavor == "SOUR":
        if info["swept_low"] and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 52):
            if not (h1_bear and h4_bear):
                return "BUY", "SOUR-TRAP"

        if info["swept_high"] and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 48):
            if not (h1_bull and h4_bull):
                return "SELL", "SOUR-TRAP"

    # 3. โหมดรสเค็ม (SALTY -> ตลาดไซด์เวย์ CHOP สูง ราคาฉีกออกนอกกรอบแล้วแรงส่งเดิมหมดลง)
    if flavor == "SALTY":
        # แรงขายเริ่มหมด (p_accel > 0 = อนุพันธ์อันดับ 2 พลิกเป็นบวก) ที่ขอบล่าง
        if (info["prev_z"] <= -1.50) and (p_accel > 0.0) and (close_p > open_p) and (vwrsi_v > prev_rsi) and (vwrsi_v <= 46):
            if not (h1_bear and h4_bear):
                return "BUY", "SALTY-MR"

        # แรงซื้อเริ่มหมด (p_accel < 0 = อนุพันธ์อันดับ 2 พลิกเป็นลบ) ที่ขอบบน
        if (info["prev_z"] >= 1.50) and (p_accel < 0.0) and (close_p < open_p) and (vwrsi_v < prev_rsi) and (vwrsi_v >= 54):
            if not (h1_bull and h4_bull):
                return "SELL", "SALTY-MR"

    return None, ""
