INITIAL_CAPITAL = 100000.0

BASE_RISK_PCT = 0.35          # ไม้ที่ 1: เสี่ยงมาตรฐาน 0.35% ($350)
CONVICTION_RISK_PCT = 0.50    # ไม้ที่ 1 (+OI): เสี่ยง 0.50% ($500)
THROTTLED_RISK_PCT = 0.25     # ช่วงแพ้ติดกัน 2 วัน: ลดเหลือ 0.25% ($250)

HOUSE_MONEY_MODE = True       # เปิดโหมดยิงต่อเมื่อชนะ TP (ไม้ที่ 2 และ 3 ลด Risk เหลือ 50% เท่ากัน)
MAX_TRADES_PER_DAY = 3

DAILY_TARGET_PCT = 0.25
HARD_DAILY_DD_PCT = 2.00
MAX_OVERALL_DD_LIMIT = 10.00
STOP_ON_BE_PLUS = True
COMMISSION_PER_OZ = 0.035

# คืนค่า BE_TRIGGER_R = 1.35 เพื่อไม่ตัดไม้ TP ก้อนใหญ่ทิ้งกลางทาง
ATR_LEN = 14
VWRSI_LEN = 14
H1_EMA_LEN = 34
SL_ATR_MULT = 2.2
TP_ATR_MULT = 3.5
BE_TRIGGER_R = 1.35           # ปกติ: วิ่งบวก 1.35R ค่อยย้าย SL มาล็อกหน้าทุน BE+
LATE_BE_TRIGGER_R = 0.65      # หลัง 23:30 น. ไทย: หากไม้ค้างดึกเคยบวก 0.65R ให้ล็อก BE+ กันไหลกลับก่อน 03:00 น.

HISTORY_CSV = "data/xauusd_m15_history.csv"
TRADES_CSV = "data/all_trades.csv"
STATE_JSON = "data/state.json"
