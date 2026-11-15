"""
Quant Engine (Upgraded Zero-Risk Profit Boost & NY Fallback Edition)
====================================================================
ไฟล์นี้รวบรวมโค้ดส่วนที่ต้องแก้ไขทั้งหมด 4 จุดหลัก เพื่อ:
1. กรอง SWEET-VWAP ช่วงเวลาเสี่ยง (05:00-07:00 UTC และ 12:00-13:00 UTC) ให้ต้องมี +OI ยืนยันเท่านั้น
   และสลับให้ SALTY-MR / SOUR-TRAP ทำงานแทนเมื่อไม่มี +OI (ตัดขาดทุน -$1,965+)
2. ล็อกเงื่อนไขไม้สอง (H2 House Money) ให้เปิดได้เฉพาะเมื่อมี +OI ยืนยันเท่านั้น (ตัดขาดทุน -$556+)
3. เพิ่มหน้าต่าง NY Session Fallback (13:00-16:30 UTC) ผ่อนปรนเกณฑ์ดึงกลับ 15% เฉพาะวันที่ยังไม่มีไม้แรก
   (trades_today == 0) เพื่อเพิ่มจำนวนวันออกไม้จาก 53% สู่ระดับ 75-85% โดยไม่เพิ่มความเสี่ยงรายวัน
4. อัปเกรดระบบจัดการออเดอร์ TP1+BE+ ด้วย Step-Lock Trailing (1.5R -> ล็อก SL ที่ TP1)
   เพื่อดึงกำไรส่วนเพิ่มจากไม้ที่ย่อกลับหลังชน TP1 โดยไม่เพิ่มขนาด Lot
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd


# ==============================================================================
# [จุดแก้ไขที่ 1] ฟังก์ชันคัดกรองสัญญาณ SWEET-VWAP รายชั่วโมง + NY Session Fallback
# นำไปแทนที่ส่วน Signal Evaluation / Regime Routing ใน quant_engine.py
# ==============================================================================
def evaluate_upgraded_signal(
    bar: pd.Series,
    prev_bar: pd.Series,
    hour_utc: int,
    trades_today: int,
    h1_closed_tp_today: bool,
    h1_direction_today: Optional[str],
    minutes_since_h1_exit: float,
) -> Tuple[Optional[str], Optional[str], bool, bool]:
    """
    คืนค่า: (direction, flavor_tag, has_oi, is_h2)
    - direction: 'BUY' | 'SELL' | None
    - flavor_tag: 'SWEET-VWAP' | 'SOUR-TRAP' | 'SALTY-MR' | None
    - has_oi: True หากมี COMEX OI / Volume Flow ยืนยัน (+OI)
    - is_h2: True หากเป็นไม้สอง (House Money H2)
    """
    has_oi = bool(bar.get("has_oi", False))
    z_score = float(bar.get("z_score", 0.0))
    atr = float(bar.get("atr", 2.5))
    close_p = float(bar["close"])
    open_p = float(bar["open"])
    high_p = float(bar["high"])
    low_p = float(bar["low"])
    vwap_p = float(bar.get("vwap", close_p))
    tenkan = float(bar.get("tenkan", close_p))
    kijun = float(bar.get("kijun", close_p))

    # --------------------------------------------------------------------------
    # [UPGRADE #3] NY Session Fallback Window (13:00 - 16:30 UTC)
    # หากถึงช่วงตลาดอเมริกาแล้วยังไม่มีออเดอร์แรกของวัน (trades_today == 0)
    # ผ่อนปรนระยะ Pullback / Z-Score ลง 15% (คูณตัวคูณ 0.85) เพื่อเก็บวันเทรดที่หายไป
    # --------------------------------------------------------------------------
    is_ny_fallback = (13 <= hour_utc <= 16) and (trades_today == 0)
    relax_factor = 0.85 if is_ny_fallback else 1.00

    # เกณฑ์ Z-Score และ Sweep ที่ปรับตามสถานะ NY Fallback
    sweet_z_thresh = 0.50 * relax_factor       # ปกติ 0.50 -> NY Fallback 0.425
    salty_z_thresh = 2.00 * relax_factor       # ปกติ 2.00 -> NY Fallback 1.70
    sweep_wick_tol = 0.05 * atr if is_ny_fallback else 0.0

    # --------------------------------------------------------------------------
    # [UPGRADE #2] กฎเหล็กสำหรับไม้สอง (H2 House Money)
    # เปิด H2 ได้เฉพาะเมื่อ:
    # 1) ไม้แรก (H1) ปิด TP สำเร็จในวันเดียวกัน (h1_closed_tp_today == True)
    # 2) พัก Cooldown ครบ >= 60 นาที (minutes_since_h1_exit >= 60)
    # 3) ต้องมี +OI ยืนยันเท่านั้น (has_oi == True) -> ตัดไม้ H2 ที่ไม่มี OI ซึ่งแพ้ 100%
    # --------------------------------------------------------------------------
    if trades_today == 1 and h1_closed_tp_today:
        if minutes_since_h1_exit < 60 or not has_oi:
            return None, None, has_oi, False

    # --------------------------------------------------------------------------
    # [UPGRADE #1] กรองหลุมดำ SWEET-VWAP ช่วง 05:00-07:00 UTC และ 12:00-13:00 UTC
    # ช่วงเวลาดังกล่าว ห้ามยิง SWEET-VWAP ถ้าไม่มี +OI ยืนยันเด็ดขาด
    # --------------------------------------------------------------------------
    is_sweet_deadzone = hour_utc in (5, 6, 7, 12, 13)
    allow_sweet = True if (not is_sweet_deadzone or has_oi) else False

    # ตรวจสอบสัญญาณดิบของแต่ละท่า (ใช้ทั้งค่า boolean สำเร็จรูปหรือคำนวณจากราคา)
    raw_sweet_buy = bar.get("signal_sweet_buy", False) or (
        close_p > vwap_p and tenkan > kijun and z_score >= sweet_z_thresh and close_p > open_p
    )
    raw_sweet_sell = bar.get("signal_sweet_sell", False) or (
        close_p < vwap_p and tenkan < kijun and z_score <= -sweet_z_thresh and close_p < open_p
    )

    raw_sour_buy = bar.get("signal_sour_buy", False) or (
        low_p <= (float(prev_bar["low"]) + sweep_wick_tol) and close_p > float(prev_bar["low"])
    )
    raw_sour_sell = bar.get("signal_sour_sell", False) or (
        high_p >= (float(prev_bar["high"]) - sweep_wick_tol) and close_p < float(prev_bar["high"])
    )

    raw_salty_buy = bar.get("signal_salty_buy", False) or (
        z_score <= -salty_z_thresh and close_p > (low_p + 0.25 * atr)
    )
    raw_salty_sell = bar.get("signal_salty_sell", False) or (
        z_score >= salty_z_thresh and close_p < (high_p - 0.25 * atr)
    )

    direction = None
    flavor_tag = None

    # ลำดับการเลือกท่าเทรด:
    # ถ้าระบบอยู่ในช่วง Deadzone ของ SWEET และไม่มี OI ให้ข้าม SWEET ไปเช็ก SOUR / SALTY ทันที
    if allow_sweet and raw_sweet_buy:
        direction, flavor_tag = "BUY", "SWEET-VWAP"
    elif allow_sweet and raw_sweet_sell:
        direction, flavor_tag = "SELL", "SWEET-VWAP"
    elif raw_sour_buy:
        direction, flavor_tag = "BUY", "SOUR-TRAP"
    elif raw_sour_sell:
        direction, flavor_tag = "SELL", "SOUR-TRAP"
    elif raw_salty_buy:
        direction, flavor_tag = "BUY", "SALTY-MR"
    elif raw_salty_sell:
        direction, flavor_tag = "SELL", "SALTY-MR"

    if direction is None:
        return None, None, has_oi, False

    # หากเป็นไม้ที่ 2 ของวัน (H2) บังคับทิศทางเดียวกับไม้แรก (Direction Lock)
    is_h2 = (trades_today == 1 and h1_closed_tp_today)
    if is_h2 and h1_direction_today is not None and direction != h1_direction_today:
        return None, None, has_oi, False

    return direction, flavor_tag, has_oi, is_h2


# ==============================================================================
# [จุดแก้ไขที่ 2] ฟังก์ชันอัปเดตออเดอร์และ Step-Lock Trailing (แก้ปัญหา TP1+BE+ ได้น้อย)
# นำไปแทนที่บล็อกเช็ก TP1 / BE+ / TP2 ในลูปจัดการออเดอร์ (Manage Active Position)
# ==============================================================================
def update_active_trade_with_steplock(
    trade: Dict[str, Any],
    high_p: float,
    low_p: float,
    close_p: float,
    hour_utc: int,
    minute_utc: int,
    be_buffer: float = 0.35,
    steplock_trigger_ratio: float = 0.50,
    steplock_lock_ratio: float = 0.85,
) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    """
    จัดการออเดอร์ที่เปิดอยู่ด้วยระบบ 3 ขั้น:
    - ขั้นที่ 1 (ชน TP1): ปิดทำกำไรครึ่งแรก 50% และขยับ SL ของครึ่งหลังมาหน้าทุน + Buffer (BE+)
    - ขั้นที่ 2 [UPGRADE #4] (Step-Lock Trailing): เมื่อราคาวิ่งเลยกึ่งกลางระหว่าง TP1 ไปหา TP2
      (steplock_trigger_ratio = 50% ของระยะ TP1->TP2 หรือราว 1.5R)
      ขยับ SL ของไม้ครึ่งหลังขึ้นไปล็อกกำไรที่ 85%-100% ของระดับ TP1 ทันที!
    - ขั้นที่ 3 (ชน TP2 หรือถอยชน SL/BE+/Step-Lock หรือตัดจบ Rollover)

    คืนค่า: (exit_suffix, weighted_exit_price, realized_pnl_usd)
    หากยังไม่ปิดออเดอร์ คืนค่า (None, None, None)
    """
    pos_type = trade["type"]
    entry_p = trade["entry"]
    sl_p = trade["sl"]
    tp1_p = trade["tp1"]
    tp2_p = trade["tp2"]
    lot_total = trade["lot_total"]
    contract_size = trade.get("contract_size", 100.0)  # XAUUSD 1 lot = 100 oz

    # 1. ตรวจสอบ Rollover Cut-off (20:00 - 20:55 UTC ป้องกันถือข้ามคืน)
    if hour_utc == 20 and minute_utc >= 0:
        if trade.get("tp1_hit", False):
            # ครึ่งแรกปิดที่ TP1 ไปแล้ว ครึ่งหลังปิดที่ราคาตลาด Rollover
            weighted_exit = 0.5 * tp1_p + 0.5 * close_p
            pts = (weighted_exit - entry_p) if pos_type == "BUY" else (entry_p - weighted_exit)
            pnl = pts * lot_total * contract_size
            return "TP1+Rollover", weighted_exit, pnl
        else:
            pts = (close_p - entry_p) if pos_type == "BUY" else (entry_p - close_p)
            pnl = pts * lot_total * contract_size
            return "Rollover", close_p, pnl

    # 2. กรณีฝั่ง BUY
    if pos_type == "BUY":
        # 2.1 เช็กว่าชน TP1 หรือยัง
        if not trade.get("tp1_hit", False) and high_p >= tp1_p:
            trade["tp1_hit"] = True
            # ย้าย SL มาที่หน้าทุน + Buffer (BE+)
            trade["sl"] = max(sl_p, entry_p + be_buffer)
            sl_p = trade["sl"]

        # 2.2 [UPGRADE #4] Step-Lock Trailing หลังชน TP1 แล้ว
        if trade.get("tp1_hit", False):
            steplock_trigger = tp1_p + steplock_trigger_ratio * (tp2_p - tp1_p)
            if high_p >= steplock_trigger:
                locked_sl = entry_p + steplock_lock_ratio * (tp1_p - entry_p)
                trade["sl"] = max(trade["sl"], locked_sl)
                sl_p = trade["sl"]

        # 2.3 เช็กว่าชนเป้าสุดท้าย TP2 หรือยัง
        if trade.get("tp1_hit", False) and high_p >= tp2_p:
            weighted_exit = 0.5 * tp1_p + 0.5 * tp2_p
            pts = weighted_exit - entry_p
            pnl = pts * lot_total * contract_size
            return "TP1+TP2", weighted_exit, pnl

        # 2.4 เช็กว่าถอยลงมาชน SL / BE+ / Step-Lock หรือไม่
        if low_p <= sl_p:
            if trade.get("tp1_hit", False):
                weighted_exit = 0.5 * tp1_p + 0.5 * sl_p
                pts = weighted_exit - entry_p
                pnl = pts * lot_total * contract_size
                return "TP1+BE+", weighted_exit, pnl
            else:
                pts = sl_p - entry_p
                pnl = pts * lot_total * contract_size
                suffix = "BE+" if sl_p > entry_p else "SL"
                return suffix, sl_p, pnl

    # 3. กรณีฝั่ง SELL
    elif pos_type == "SELL":
        # 3.1 เช็กว่าชน TP1 หรือยัง
        if not trade.get("tp1_hit", False) and low_p <= tp1_p:
            trade["tp1_hit"] = True
            # ย้าย SL มาที่หน้าทุน - Buffer (BE+)
            trade["sl"] = min(sl_p, entry_p - be_buffer)
            sl_p = trade["sl"]

        # 3.2 [UPGRADE #4] Step-Lock Trailing หลังชน TP1 แล้ว
        if trade.get("tp1_hit", False):
            steplock_trigger = tp1_p - steplock_trigger_ratio * (entry_p - tp2_p - (entry_p - tp1_p))
            if low_p <= steplock_trigger:
                locked_sl = entry_p - steplock_lock_ratio * (entry_p - tp1_p)
                trade["sl"] = min(trade["sl"], locked_sl)
                sl_p = trade["sl"]

        # 3.3 เช็กว่าชนเป้าสุดท้าย TP2 หรือยัง
        if trade.get("tp1_hit", False) and low_p <= tp2_p:
            weighted_exit = 0.5 * tp1_p + 0.5 * tp2_p
            pts = entry_p - weighted_exit
            pnl = pts * lot_total * contract_size
            return "TP1+TP2", weighted_exit, pnl

        # 3.4 เช็กว่าดีดขึ้นไปชน SL / BE+ / Step-Lock หรือไม่
        if high_p >= sl_p:
            if trade.get("tp1_hit", False):
                weighted_exit = 0.5 * tp1_p + 0.5 * sl_p
                pts = entry_p - weighted_exit
                pnl = pts * lot_total * contract_size
                return "TP1+BE+", weighted_exit, pnl
            else:
                pts = entry_p - sl_p
                pnl = pts * lot_total * contract_size
                suffix = "BE+" if sl_p < entry_p else "SL"
                return suffix, sl_p, pnl

    return None, None, None


# ==============================================================================
# [จุดแก้ไขที่ 3] ฟังก์ชันประกอบชื่อ Reason Tag และการคำนวณ Risk Sizing (ไม่เพิ่มความเสี่ยง)
# ==============================================================================
def build_reason_tag(flavor_tag: str, has_oi: bool, is_h2: bool, exit_suffix: str) -> str:
    """
    สร้างสตริงคอลัมน์ `reason` ให้ตรงกับฟอร์แมตใน all_trades.csv เช่น:
    - SWEET-VWAP+OI-TP1+TP2
    - SOUR-TRAP-TP1+BE+
    - SWEET-VWAP+OI-H2-TP1+BE+
    - Rollover
    """
    if exit_suffix == "Rollover":
        return "Rollover"
    oi_part = "+OI" if has_oi else ""
    h2_part = "-H2" if is_h2 else ""
    return f"{flavor_tag}{oi_part}{h2_part}-{exit_suffix}"


def calculate_zero_extra_risk_lot(
    equity: float,
    entry_price: float,
    sl_price: float,
    has_oi: bool,
    is_h2: bool,
    base_risk_pct: float = 0.0035,
    no_oi_risk_pct: float = 0.0025,
    contract_size: float = 100.0,
) -> float:
    """
    คำนวณขนาด Lot โดยไม่เพิ่มเพดานความเสี่ยง:
    - หากมี +OI ยืนยัน ใช้ความเสี่ยงมาตรฐาน (เช่น 0.35% หรือ ~$350-$380 บนพอร์ต $100k)
    - หากไม่มี +OI ใช้ความเสี่ยงลดหลั่น (เช่น 0.25% หรือ ~$250)
    - หากเป็นไม้ H2 (House Money) ลดความเสี่ยงลงครึ่งหนึ่งเสมอ (x 0.5)
    """
    risk_pct = base_risk_pct if has_oi else no_oi_risk_pct
    if is_h2:
        risk_pct *= 0.50

    sl_dist = abs(entry_price - sl_price)
    if sl_dist <= 0:
        return 0.01

    risk_usd = equity * risk_pct
    lot = risk_usd / (sl_dist * contract_size)
    return max(0.01, round(lot, 2))


# ==============================================================================
# [จุดแก้ไขที่ 4] ลูป Backtest หลักที่รวมการอัปเกรดทั้งหมดเข้าด้วยกัน (Drop-in Replacement)
# สามารถนำไปแทนที่ฟังก์ชัน run_backtest(df) เดิมใน quant_engine.py ได้ทันที
# ==============================================================================
def run_backtest(
    df: pd.DataFrame,
    initial_balance: float = 100000.0,
    export_csv_path: str = "all_trades.csv",
) -> pd.DataFrame:
    """
    รัน Backtest พร้อมตรรกะอัปเกรดทั้ง 4 ส่วน และส่งออกไฟล์ all_trades.csv
    ด้วยคอลัมน์: entry_str, exit_str, entry_time, exit_time, entry_hour_utc, type, entry, exit, pnl, reason
    """
    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        time_col = "time" if "time" in df.columns else "timestamp"
        df[time_col] = pd.to_datetime(df[time_col], utc=True)
        df.set_index(time_col, inplace=True)
    else:
        df.index = df.index.tz_localize("UTC") if df.index.tz is None else df.index.tz_convert("UTC")

    equity = initial_balance
    all_trades = []
    current_trade: Optional[Dict[str, Any]] = None

    # ตัวแปรติดตามสถานะรายวันสำหรับ NY Fallback และ H2 House Money
    current_day = None
    trades_today = 0
    h1_closed_tp_today = False
    h1_direction_today: Optional[str] = None
    last_h1_exit_time: Optional[pd.Timestamp] = None

    for i in range(1, len(df)):
        bar = df.iloc[i]
        prev_bar = df.iloc[i - 1]
        t: pd.Timestamp = df.index[i]

        # รีเซ็ตตัวนับเมื่อขึ้นวันใหม่ (ตามเวลา UTC)
        if current_day != t.date():
            current_day = t.date()
            trades_today = 0
            h1_closed_tp_today = False
            h1_direction_today = None
            last_h1_exit_time = None

        # ----------------------------------------------------------------------
        # ส่วนที่ 1: บริหารออเดอร์ที่ถืออยู่ (TP1 -> BE+ -> Step-Lock Trailing -> TP2)
        # ----------------------------------------------------------------------
        if current_trade is not None:
            exit_suffix, exit_price, pnl_usd = update_active_trade_with_steplock(
                trade=current_trade,
                high_p=float(bar["high"]),
                low_p=float(bar["low"]),
                close_p=float(bar["close"]),
                hour_utc=t.hour,
                minute_utc=t.minute,
            )

            if exit_suffix is not None and exit_price is not None and pnl_usd is not None:
                equity += pnl_usd
                reason_str = build_reason_tag(
                    flavor_tag=current_trade["flavor_tag"],
                    has_oi=current_trade["has_oi"],
                    is_h2=current_trade["is_h2"],
                    exit_suffix=exit_suffix,
                )

                entry_ts_code = int(current_trade["entry_time"].timestamp() // 1000)
                exit_ts_code = int(t.timestamp() // 1000)

                all_trades.append(
                    {
                        "entry_str": current_trade["entry_time"].strftime("%Y-%m-%d %H:%M"),
                        "exit_str": t.strftime("%Y-%m-%d %H:%M"),
                        "entry_time": entry_ts_code,
                        "exit_time": exit_ts_code,
                        "entry_hour_utc": current_trade["entry_time"].hour,
                        "type": current_trade["type"],
                        "entry": round(float(current_trade["entry"]), 2),
                        "exit": round(float(exit_price), 2),
                        "pnl": round(float(pnl_usd), 2),
                        "reason": reason_str,
                    }
                )

                # หากไม้แรก (H1) ปิดกำไรด้วย TP1+BE+ หรือ TP1+TP2 ให้ปลดล็อกสิทธิ์ H2 ของวันนั้น
                if not current_trade["is_h2"] and ("TP1" in exit_suffix):
                    h1_closed_tp_today = True
                    h1_direction_today = current_trade["type"]
                    last_h1_exit_time = t

                current_trade = None

        # ----------------------------------------------------------------------
        # ส่วนที่ 2: ตรวจหาสัญญาณเปิดออเดอร์ใหม่ (สูงสุดไม่เกิน 2 ไม้/วัน คือ H1 และ H2)
        # ----------------------------------------------------------------------
        if current_trade is None and trades_today < 2:
            # ข้ามช่วงเวลาตลาดวาย / พัก Rollover (17:00 - 01:59 UTC)
            if t.hour >= 17 or t.hour < 2:
                continue

            minutes_since_h1 = (
                (t - last_h1_exit_time).total_seconds() / 60.0
                if last_h1_exit_time is not None
                else 0.0
            )

            direction, flavor_tag, has_oi, is_h2 = evaluate_upgraded_signal(
                bar=bar,
                prev_bar=prev_bar,
                hour_utc=t.hour,
                trades_today=trades_today,
                h1_closed_tp_today=h1_closed_tp_today,
                h1_direction_today=h1_direction_today,
                minutes_since_h1_exit=minutes_since_h1,
            )

            if direction is not None and flavor_tag is not None:
                entry_p = float(bar["close"])
                atr = float(bar.get("atr", 2.5))

                # กำหนดระยะ SL / TP1 / TP2 ตามแต่ละท่าเทรด
                if flavor_tag == "SWEET-VWAP":
                    sl_dist = 1.5 * atr
                    tp1_dist = 1.0 * sl_dist
                    tp2_dist = 2.0 * sl_dist
                elif flavor_tag == "SOUR-TRAP":
                    sl_dist = max(0.8 * atr, abs(entry_p - float(bar["low" if direction == "BUY" else "high"])) + 0.3 * atr)
                    tp1_dist = 1.0 * sl_dist
                    tp2_dist = 1.8 * sl_dist
                else:  # SALTY-MR
                    sl_dist = 1.2 * atr
                    tp1_dist = 1.0 * sl_dist
                    tp2_dist = 1.6 * sl_dist

                sl_p = (entry_p - sl_dist) if direction == "BUY" else (entry_p + sl_dist)
                tp1_p = (entry_p + tp1_dist) if direction == "BUY" else (entry_p - tp1_dist)
                tp2_p = (entry_p + tp2_dist) if direction == "BUY" else (entry_p - tp2_dist)

                lot_total = calculate_zero_extra_risk_lot(
                    equity=equity,
                    entry_price=entry_p,
                    sl_price=sl_p,
                    has_oi=has_oi,
                    is_h2=is_h2,
                )

                current_trade = {
                    "flavor_tag": flavor_tag,
                    "type": direction,
                    "has_oi": has_oi,
                    "is_h2": is_h2,
                    "entry": entry_p,
                    "entry_time": t,
                    "sl": sl_p,
                    "tp1": tp1_p,
                    "tp2": tp2_p,
                    "lot_total": lot_total,
                    "tp1_hit": False,
                }
                trades_today += 1

    trades_df = pd.DataFrame(
        all_trades,
        columns=[
            "entry_str",
            "exit_str",
            "entry_time",
            "exit_time",
            "entry_hour_utc",
            "type",
            "entry",
            "exit",
            "pnl",
            "reason",
        ],
    )
    if export_csv_path:
        trades_df.to_csv(export_csv_path, index=False)
    return trades_df
