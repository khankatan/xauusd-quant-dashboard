INITIAL_CAPITAL = 100000.0

BASE_RISK_PCT = 0.35          
CONVICTION_RISK_PCT = 0.38    
THROTTLED_RISK_PCT = 0.25     

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

SL_ATR_MULT = 2.0             
TP_ATR_MULT = 3.0             
BE_TRIGGER_R = 1.15           
PARTIAL_TP_RATIO = 0.50       
BE_BUFFER_ATR = 0.08          
LATE_BE_TRIGGER_R = 0.65      

# --- เพิ่มกฎข้อ 4: Step-Lock Trailing ---
STEP_LOCK_TRIGGER_R = 1.5     # เมื่อราคาวิ่งไปถึง 1.5R ขยับ SL ล็อกกำไรที่ TP1 (1.15R) ทันที
STEP_LOCK_LOCK_R = 1.15       # ล็อกกำไรไว้ที่ระดับ TP1

# --- เพิ่มกฎข้อ 3: NY Session Fallback Window (13:00 - 16:30 UTC) ---
FALLBACK_START_HOUR = 13      # 20:00 น. เวลาไทย
FALLBACK_END_HOUR = 16        # 23:30 น. เวลาไทย
FALLBACK_PULLBACK_REDUCE = 0.125 # ผ่อนปรนระยะดึงกลับ 12.5%

HISTORY_CSV = "data/xauusd_m15_history.csv"
TRADES_CSV = "data/all_trades.csv"
STATE_JSON = "data/state.json"
