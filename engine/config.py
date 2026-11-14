# เส้นประสาทกลาง: ศูนย์รวมค่าพารามิเตอร์และกฎเหล็ก FTMO (Max Daily DD < 3%, Max Overall DD < 10%)
INITIAL_CAPITAL = 100000.0

# กฎการบริหารความเสี่ยงแบบ Dynamic Conviction
BASE_RISK_PCT = 0.35          # เสี่ยงมาตรฐาน 0.35% ($350) ต่อไม้
CONVICTION_RISK_PCT = 0.50    # เพิ่ม Risk เป็น 0.50% ($500) ในวันที่ OI/Volume และ DXY ยืนยันเทรนด์จริง
THROTTLED_RISK_PCT = 0.25     # ลดเหลือ 0.25% ทันทีเมื่อแพ้ติดกัน 2 ครั้งขึ้นไป

DAILY_TARGET_PCT = 0.25       # เป้ากำไรรายวัน +0.25% -> ถึงแล้วล็อกกำไรหยุดเทรดทันที!
HARD_DAILY_DD_PCT = 2.00      # Circuit Breaker รายวัน (-2.00% คุมเข้มไม่ให้แตะเพดาน 3.00% เด็ดขาด)
MAX_OVERALL_DD_LIMIT = 10.00  # เพดานขาดทุนรวม FTMO 10% จากเงินต้น ($100,000 -> ห้ามต่ำกว่า $90,000)
MAX_TRADES_PER_DAY = 1        # ยิงวันละ 1 นัดคมๆ ทุกวันทำการ
STOP_ON_BE_PLUS = True        # วันไหนชน BE+ ให้หยุดพักทันที รอวันถัดไป
COMMISSION_PER_OZ = 0.035

# พารามิเตอร์อินดิเคเตอร์และระยะ SL/TP (ชุดทำกำไร +$1,452 / PF 1.39 จาก V6)
ATR_LEN = 14
VWRSI_LEN = 14
H1_EMA_LEN = 34
SL_ATR_MULT = 2.2
TP_ATR_MULT = 3.5             # R:R 1:1.59 -> ชนะไม้ Conviction 0.50% ได้กำไร ~+0.79% (+$790) ในไม้เดียว!
BE_TRIGGER_R = 1.35

# ไฟล์จัดเก็บข้อมูล
HISTORY_CSV = "data/xauusd_m15_history.csv"
TRADES_CSV = "data/all_trades.csv"
STATE_JSON = "data/state.json"
