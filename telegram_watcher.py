import os
import json
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta

STATE_JSON = "data/state.json"
TRADES_CSV = "data/all_trades.csv"
ALERT_MEMORY = "data/tg_sent_memory.json"

def send_tg(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("[TG-SKIP] ไม่พบ TELEGRAM_BOT_TOKEN หรือ TELEGRAM_CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        return res.status_code == 200
    except Exception as e:
        print(f"[TG-ERROR] {e}")
        return False

def load_memory():
    if os.path.exists(ALERT_MEMORY):
        try:
            with open(ALERT_MEMORY, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "active_trade_id": None,
        "sent_entry": False,
        "sent_be": False,
        "sent_steplock": False,
        "last_closed_exit_time": None,
        "last_heartbeat_date": None
    }

def save_memory(mem):
    os.makedirs(os.path.dirname(ALERT_MEMORY), exist_ok=True)
    with open(ALERT_MEMORY, "w", encoding="utf-8") as f:
        json.dump(mem, f, indent=2)

def check_and_notify():
    if not os.path.exists(STATE_JSON):
        return

    with open(STATE_JSON, "r", encoding="utf-8") as f:
        state = json.load(f)

    sig = state.get("signal", {})
    sig_type = str(sig.get("type", "WAIT"))
    agent_txt = str(sig.get("agent", ""))
    mem = load_memory()

    # 0. ส่งข้อความเช็กสถานะบอททุกเช้าเวลา 07:00 น. เวลาไทย (วันจันทร์-ศุกร์) พร้อมบอกวันที่
    thai_now = datetime.now(timezone.utc) + timedelta(hours=7)
    today_str = thai_now.strftime("%Y-%m-%d")
    thai_days = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
    day_name = thai_days[thai_now.weekday()]

    if thai_now.weekday() < 5 and thai_now.hour == 7 and thai_now.minute < 15:
        if mem.get("last_heartbeat_date") != today_str:
            hb_msg = (
                f"☀️ <b>MORNING CHECK-IN: บอททำงานปกติ (24/7)</b>\n"
                f"📅 <b>วัน{day_name}ที่ {thai_now.strftime('%d/%m/%Y')}</b> | เวลา: {thai_now.strftime('%H:%M')} น.\n"
                f"⏳ สถานะระบบ: พร้อมทำงาน (เริ่มเปิดรับสัญญาณเทรด 09:30 น. เป็นต้นไป)"
            )
            if send_tg(hb_msg):
                mem["last_heartbeat_date"] = today_str
                save_memory(mem)

    # 1. กรณีมีสัญญาณเข้าใหม่ (BUY / SELL) หรือกำลังถือออเดอร์ (HOLD BUY / HOLD SELL)
    if sig_type in ["BUY", "SELL", "HOLD BUY", "HOLD SELL"]:
        direction = sig_type.replace("HOLD ", "")
        entry_p = sig.get("entry")
        sl_p = sig.get("sl")
        tp1_p = sig.get("tp1")
        tp2_p = sig.get("tp")
        risk_pct = sig.get("risk_pct", 0)
        lot_size = float(sig.get("lot_size", 0.0))
        half_lot = round(lot_size * 0.5, 2)

        trade_id = f"{direction}_{entry_p}"

        if mem.get("active_trade_id") != trade_id:
            mem = {
                "active_trade_id": trade_id,
                "sent_entry": False,
                "sent_be": False,
                "sent_steplock": False,
                "last_closed_exit_time": mem.get("last_closed_exit_time"),
                "last_heartbeat_date": mem.get("last_heartbeat_date")
            }

        # 1.1 แจ้งจุดเข้า Entry, SL, TP1, TP2 และขนาด Lot
        if not mem["sent_entry"]:
            msg = (
                f"🚨 <b>XAUUSD SIGNAL: {direction}</b>\n"
                f"🤖 กลยุทธ์: <code>{agent_txt.split('|')[0].strip()}</code>\n"
                f"📍 <b>จุดเข้า (Entry):</b> {entry_p}\n"
                f"🛑 <b>SL:</b> {sl_p}\n"
                f"🎯 <b>TP1 (ปิด 50% @ 1.15R):</b> {tp1_p}\n"
                f"🏆 <b>TP2 (เป้าหมายหลัก):</b> {tp2_p}\n"
                f"📦 <b>ขนาด Lot:</b> <code>{lot_size:.2f} Lot</code> (แบ่งปิด TP1: {half_lot:.2f} Lot)\n"
                f"⚖️ Risk: {risk_pct}%"
            )
            if send_tg(msg):
                mem["sent_entry"] = True

        # 1.2 แจ้งจังหวะขยับ SL ขึ้นไปอีก (Step-Lock @ 1.50R -> ล็อกที่ TP1 / 1.15R)
        if "STEP-LOCK" in agent_txt and not mem["sent_steplock"]:
            msg = (
                f"🔥 <b>STEP-LOCK TRAILING ACTIVE! ({direction})</b>\n"
                f"📈 ราคาวิ่งทะลุ <b>1.50R</b> เรียบร้อย!\n"
                f"🔒 <b>ขยับ SL ล็อกกำไรเพิ่มขึ้นมาที่ระดับ TP1 (1.15R):</b> <code>{sl_p}</code>\n"
                f"🎯 ปล่อยรันลุ้น TP2: {tp2_p} (เหลือถือ: {lot_size:.2f} Lot)"
            )
            if send_tg(msg):
                mem["sent_steplock"] = True
                mem["sent_be"] = True

        # 1.3 แจ้งจังหวะเลื่อน SL มาบังหน้าทุน (ชน TP1 หรือเงื่อนไขรอบดึก Late-Night BE)
        elif ("BE+ ACTIVE" in agent_txt or (direction == "BUY" and sl_p >= entry_p) or (direction == "SELL" and sl_p <= entry_p)) and not mem["sent_be"]:
            msg = (
                f"🛡️ <b>เลื่อน SL บังหน้าทุนเรียบร้อย ({direction})</b>\n"
                f"📍 ราคาเข้า: {entry_p} | TP1: {tp1_p}\n"
                f"🔒 <b>SL ใหม่ (กันทุน +0.08 ATR):</b> <code>{sl_p}</code>\n"
                f"🚀 ถือลุ้นเป้าหมาย TP2: {tp2_p} (เหลือถือ: {lot_size:.2f} Lot)"
            )
            if send_tg(msg):
                mem["sent_be"] = True

        save_memory(mem)

    # 2. กรณีสถานะกลับเป็น WAIT (ออเดอร์เพิ่งปิดจบไป)
    elif sig_type == "WAIT" and os.path.exists(TRADES_CSV):
        try:
            df_t = pd.read_csv(TRADES_CSV)
            if not df_t.empty:
                latest = df_t.iloc[-1]
                exit_t = int(latest["exit_time"])
                if mem.get("last_closed_exit_time") != exit_t and mem.get("active_trade_id") is not None:
                    pnl = float(latest["pnl"])
                    icon = "✅" if pnl > 0 else "❌"
                    msg = (
                        f"{icon} <b>ปิดออเดอร์เรียบร้อย ({latest['type']})</b>\n"
                        f"📌 สาเหตุ: <code>{latest['reason']}</code>\n"
                        f"📍 เข้า: {latest['entry']} ➔ ออก: {latest['exit']}\n"
                        f"💵 <b>PnL:</b> {'+' if pnl > 0 else ''}${pnl:.2f}"
                    )
                    if send_tg(msg):
                        mem["last_closed_exit_time"] = exit_t
                        mem["active_trade_id"] = None
                        save_memory(mem)
        except Exception as e:
            print(f"[CSV-READ-ERROR] {e}")

if __name__ == "__main__":
    check_and_notify()
