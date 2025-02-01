import logging
from datetime import datetime
from config.settings import TRADE_LOG, BALANCE_LOG
import os

# 로그 디렉토리 생성
os.makedirs(os.path.dirname(TRADE_LOG), exist_ok=True)
os.makedirs(os.path.dirname(BALANCE_LOG), exist_ok=True)


def init_logger():
    """로거 초기화"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(TRADE_LOG),  # 파일 핸들러
            logging.StreamHandler()          # 콘솔 핸들러
        ]
    )
    logging.info("로거 초기화 완료")

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(TRADE_LOG),  # 파일 핸들러
        logging.StreamHandler()          # 콘솔 핸들러
    ]
)

logger = logging.getLogger(__name__)

def log_trade(symbol, side, price, quantity):
    """
    거래 내역을 로그 파일과 콘솔에 기록합니다.
    
    :param symbol: 코인 심볼 (예: 'BTCUSDT')
    :param side: 주문 방향 (예: 'BUY' 또는 'SELL')
    :param price: 주문 가격
    :param quantity: 주문 수량
    """
    log_message = (
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"거래 완료 - {symbol} {side} {quantity}@{price}"
    )
    logger.info(log_message)

def log_balance(balance_data):
    """
    잔고 정보를 로그 파일과 콘솔에 기록합니다.
    
    :param balance_data: 잔고 정보 딕셔너리
    """
    log_message = (
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
        f"잔고 정보 - {balance_data}"
    )
    logger.info(log_message)