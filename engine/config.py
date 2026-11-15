INITIAL_CAPITAL = 100000.0

BASE_RISK_PCT = 0.35          # เสี่ยงมาตรฐาน 0.35% ($350) ต่อไม้
CONVICTION_RISK_PCT = 0.38    # เสี่ยง 0.38% เมื่อมี +OI หนุนหลัง
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

# ระบบแบ่งปิดกำไร 50% (Scale-Out TP1) + กันหน้าทุน BE+ ที่ระยะปลอดภัยเดิม (0.08 ATR)
SL_ATR_MULT = 2.0             # ระยะ SL มาตรฐาน 2.0 ATR
TP_ATR_MULT = 3.0             # ระยะ TP2 (Runner 50% ที่เหลือ) 3.0 ATR
BE_TRIGGER_R = 1.15           # จุด TP1 (ระยะ 1.15 R): แบ่งปิดกำไร 50% ทันที + เลื่อน SL บังทุน
PARTIAL_TP_RATIO = 0.50       # สัดส่วนการแบ่งปิดกำไรที่จุด TP1 (50% ของ Lot ทั้งหมด)
BE_BUFFER_ATR = 0.08          # ระยะกันหน้าทุนเดิม (0.08 ATR) เพื่อไม่ให้ทองสะบัดไส้เทียนมากินก่อนไป TP2
LATE_BE_TRIGGER_R = 0.65      # หากหลัง 23:30 น. ยังไม่ถึง TP1 แต่บวกเกิน 0.65 R ให้เลื่อน SL บังทุนปลอดภัยไว้ก่อน

HISTORY_CSV = "data/xauusd_m15_history.csv"
TRADES_CSV = "data/all_trades.csv"
STATE_JSON = "data/state.json"
