import time
from datetime import datetime, timezone
from quant_engine import run_modular_engine
from telegram_watcher import check_and_notify

print("🚀 Starting XAUUSD Quant Live Runner (M15 Sync)...")

# รันครั้งแรกทันทีเมื่อเปิดบอท
run_modular_engine()
check_and_notify()

while True:
    now = datetime.now(timezone.utc)
    mins_to_next = 15 - (now.minute % 15)
    sleep_seconds = (mins_to_next * 60) - now.second + 3
    if sleep_seconds <= 0:
        sleep_seconds += 900

    print(f"[{now.strftime('%H:%M:%S')} UTC] Waiting {sleep_seconds}s for next M15 close...")
    time.sleep(sleep_seconds)

    try:
        run_modular_engine()
        check_and_notify()
    except Exception as e:
        print(f"[RUNNER ERROR] {e}")
        time.sleep(10)
