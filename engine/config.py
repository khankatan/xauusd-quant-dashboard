INITIAL_CAPITAL = 100000.0

BASE_RISK_PCT = 0.35          # เสี่ยงมาตรฐาน 0.35% ($350) ต่อไม้
CONVICTION_RISK_PCT = 0.38    # จูนจาก 0.50% ลงเป็น 0.38% เพื่อคุมความแปรปรวนของไม้แพ้ไม่ให้เกิน -$380
THROTTLED_RISK_PCT = 0.25     # ลดเหลือ 0.25% เมื่อแพ้ติดกัน 2 วันขึ้นไป

HOUSE_MONEY_MODE = True
MAX_TRADES_PER_DAY = 3

DAILY_TARGET_PCT = 0.25
HARD_DAILY_DD_PCT = 2.00
MAX_OVERALL_DD_LIMIT = 10.00
STOP_ON_BE_PLUS = True
COMMISSION_PER_OZ = 0.035

ATR_LEN = 14
VWRSI_LEN = 14
H1_EMA_LEN = 34

# จูนระยะ SL / TP และจุดล็อกกำไร BE+ ให้สอดคล้องกับระยะวิ่งจริงของคลื่น M15
SL_ATR_MULT = 2.0             # จูนจาก 2.2 ลงเป็น 2.0 ATR
TP_ATR_MULT = 2.7             # จูนจาก 3.5 ลงเป็น 2.7 ATR (เปลี่ยนไม้ที่เคยไปไม่ถึงฝั่งให้ชน TP จริง)
BE_TRIGGER_R = 1.15           # จูนจาก 1.35 ลงเป็น 1.15 R (ล็อกกำไรเร็วขึ้น)
LATE_BE_TRIGGER_R = 0.60

HISTORY_CSV = "data/xauusd_m15_history.csv"
TRADES_CSV = "data/all_trades.csv"
STATE_JSON = "data/state.json"
