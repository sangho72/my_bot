import subprocess
import time
from datetime import datetime, timezone, timedelta
from binance.client import Client
from config.settings import API_KEY, SECRET_KEY, KST
import logging

logger = logging.getLogger(__name__)

class TimeSync:
    def __init__(self):
        self.client = Client(API_KEY, SECRET_KEY)  # Binance 클라이언트 초기화
    
    def sync_system_time(self):
        """윈도우 시간 동기화 (기존 sync_time 함수 개선)"""
        try:
            subprocess.run("w32tm /resync", check=True, shell=True)
            logger.info(f"[{self.get_kst_time()}] 시스템 시간 동기화 완료")
        except Exception as e:
            logger.error(f"[{self.get_kst_time()}] 시간 동기화 실패: {e}")
    
    def get_kst_time(self):
        """KST 시간 문자열 반환"""
        return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
    
    def check_time_diff(self):
        """서버-로컬 시간 차이 체크 (기존 timecheck 로직 완전 재구현)"""
        try:
            server_time = self.client.get_server_time()['serverTime']
            local_time = int(time.time() * 1000)
            time_diff = local_time - server_time
            
            logger.info(f"[{self.get_kst_time()}] 시간차: {time_diff}ms")
            
            if abs(time_diff) > 500:
                logger.warning("시간 차이 500ms 초과 → 동기화 실행")
                self.sync_system_time()
                return False
            return True
        except Exception as e:
            logger.error(f"시간 차이 체크 실패: {e}")
            return False