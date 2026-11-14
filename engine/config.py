# เส้นประสาทกลาง: ศูนย์รวมค่าพารามิเตอร์และกฎเหล็กการบริหารความเสี่ยง
INITIAL_CAPITAL = 100000.0

# กฎการบริหารความเสี่ยง (คุมเข้มไม่ให้ Daily DD แตะ 3% เด็ดขาด)
BASE_RISK_PCT = 0.35          # เสี่ยงปกติ 0.35% ($350) ต่อไม้
THROTTLED_RISK_PCT = 0.20     # ลดเหลือ 0.20% ทันทีเมื่อแพ้ติดกัน 2 ครั้งขึ้นไป
DAILY_TARGET_PCT = 0.25       # เป้ากำไรรายวัน +0.25% -> ถึงแล้วล็อกกำไรหยุดเทรดทันที!
HARD_DAILY_DD_PCT = 1.50      # Circuit Breaker รายวัน (-1.50% ต่ำกว่ากฎ 3% เท่าตัว)
MAX_TRADES_PER_DAY = 1        # ยิงวันละ 1 นัดคมๆ ทุกวันทำการ (ป้องกันการแพ้เบิ้ลในวันเดียว)
STOP_ON_BE_PLUS = True        # วันไหนชน BE+ ให้หยุดพักทันที รอวันถัดไป
COMMISSION_PER_OZ = 0.035

# พารามิเตอร์อินดิเคเตอร์และระยะ SL/TP
ATR_LEN = 14
VWRSI_LEN = 14
H1_EMA_LEN = 34
SL_ATR_MULT = 1.7
TP_ATR_MULT = 2.2             # R:R ~1:1.30 -> ชนะ 1 ไม้ได้ ~+0.45% ทะลุเป้า +0.25% ทันที
BE_TRIGGER_R = 1.05

# ไฟล์จัดเก็บข้อมูล
HISTORY_CSV = "data/xauusd_m15_history.csv"
TRADES_CSV = "data/all_trades.csv"
STATE_JSON = "data/state.json"
