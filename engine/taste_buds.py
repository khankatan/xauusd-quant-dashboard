def taste_market_flavor(bar, prev, asian_high, asian_low, asian_bars):
    """
    ต่อมรับรสของตลาด (Market Tongue Sensor):
    ชิมพฤติกรรมราคา ณ แท่งปัจจุบัน แล้วส่งรหัส 'รสชาติ' (SWEET / SOUR / SALTY / BITTER)
    ไปให้สมองส่วนกลางเลือกกลยุทธ์ที่เหมาะสมที่สุด
    """
    atr_ratio = float(bar.get("atr_ratio", 1.0))
    er_v = float(bar.get("er", 0.30))
    fast_z = float(bar.get("fast_z", 0.0))
    prev_z = float(prev.get("fast_z", 0.0))

    h1_bull = float(bar["h1_close"]) >= float(bar["h1_ema"])
    h1_bear = float(bar["h1_close"]) < float(bar["h1_ema"])
    h4_bull = float(bar["h4_close"]) >= float(bar["h4_ema"])
    h4_bear = float(bar["h4_close"]) < float(bar["h4_ema"])
    mtf_aligned = (h1_bull and h4_bull) or (h1_bear and h4_bear)

    # 1. ปุ่มรับรสขม (BITTER): ข่าวกระชากผิดปกติ (> 1.85x) หรือตลาดตายสนิท (< 0.45x)
    if atr_ratio > 1.85 or atr_ratio < 0.45:
        return "BITTER", {"reason": "TOXIC_VOLATILITY"}

    # 2. ปุ่มรับรสเปรี้ยว (SOUR): ตรวจพบกับดักกวาดสภาพคล่อง (Liquidity Sweep & Rejection)
    # ราคามีการแทงทะลุกรอบ Asian High/Low หรือยืดตัวสุดโต่ง (|prev_z| >= 1.75) แล้วดีดกลับทันที
    has_asian_box = (asian_bars >= 8) and (asian_high > asian_low)
    swept_low = has_asian_box and ((float(bar["low"]) < asian_low) or (float(prev["low"]) < asian_low)) and (float(bar["close"]) > asian_low)
    swept_high = has_asian_box and ((float(bar["high"]) > asian_high) or (float(prev["high"]) > asian_high)) and (float(bar["close"]) < asian_high)
    extreme_snap = (abs(prev_z) >= 1.85) and (abs(fast_z) < abs(prev_z))

    if swept_low or swept_high or extreme_snap:
        return "SOUR", {
            "swept_low": swept_low,
            "swept_high": swept_high,
            "extreme_snap": extreme_snap,
            "prev_z": prev_z
        }

    # 3. ปุ่มรับรสหวาน (SWEET): เทรนด์สะอาด วิ่งเป็นทิศทางชัดเจน (H1+H4 ตรงกัน + ER >= 0.36)
    if mtf_aligned and (er_v >= 0.36):
        return "SWEET", {
            "bull_trend": (h1_bull and h4_bull),
            "bear_trend": (h1_bear and h4_bear),
            "er": er_v
        }

    # 4. ปุ่มรับรสเค็ม (SALTY): ตลาดแกว่งออกข้างในกรอบ (ER < 0.36) และราคาเริ่มยืดเกินค่าเฉลี่ย
    if (er_v < 0.36) and (abs(prev_z) >= 1.50):
        return "SALTY", {
            "prev_z": prev_z,
            "er": er_v
        }

    return "BITTER", {"reason": "NO_DISTINCT_FLAVOR"}
