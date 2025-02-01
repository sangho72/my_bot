import os
from datetime import timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# API 설정
API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

# 거래 설정
COIN_LIST = ['XRPUSDT','DOGEUSDT','HBARUSDT','ADAUSDT','WIFUSDT']
TRADE_RATE = 0.2
TARGET_LEVERAGE = 5
INTERVAL = "1m"
KST = timezone(timedelta(hours=9))
BASE_URL = "https://fapi.binance.com"

# 파일 경로
BALANCE_LOG = "my_bot/logs/balance_log.txt"
TRADE_LOG = "my_bot/logs/trade_log.txt"
DATA_DIR = "my_bot/data"