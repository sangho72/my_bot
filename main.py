from config.settings import COIN_LIST
from modules.data_handler import DataHandler
from modules.order_handler import OrderHandler
from strategies.basic_strategy import BasicStrategy
from modules.ws_manager import WebSocketManager
from utils.time_sync import TimeSync
from utils.logger import init_logger,log_balance
import schedule
import time

class TradingBot:
    def __init__(self):
        self.time_sync = TimeSync()  # 시간 동기화 객체 생성
        self.data_handler = DataHandler()
        self.data_handler.initialize_data() 
        self.ws_manager  = WebSocketManager(self.data_handler)
        self.order_handler  = OrderHandler(self.data_handler)
        self.strategy = BasicStrategy()
        init_logger()

    def run(self):
        self.time_sync.sync_system_time()  
        
        # 1시간마다 시간 차이 체크 (기존 스케줄러 설정)
        schedule.every(1).hour.at(":01").do(
            lambda: self.time_sync.check_time_diff()
        )

        self.check_balance()
        self.check_positions()

        self.ws_manager.start_account_websocket()  # 계정 업데이트
        self.ws_manager.start_coin_websockets()    # 코인별 3개 웹소켓

        # 기존 스케줄러 설정 유지
        # schedule.every(1).hour.do(self.check_balance)
        # schedule.every(5).minutes.do(self.check_positions)
        
        # schedule.every(1).minute.do(self.trade_cycle)
        while True:
            self.trade_cycle()
            schedule.run_pending()
            time.sleep(1)

    def trade_cycle(self):
        """매매 주기 실행"""
        for symbol in self.data_handler.coin_data.keys():
            # 데이터 가져오기
            df_1m = self.data_handler.coin_data[symbol]['1m']
            df_1h = self.data_handler.coin_data[symbol]['1h']
            
            # 지표 계산
            df_1m = self.strategy.calculate_indicators(df_1m)
            df_1h = self.strategy.calculate_indicators(df_1h)
            
            # 매매 신호 생성
            position = self.data_handler.position_data[symbol]
            signals = self.strategy.generate_trading_signals(df_1m, position)
            
            # 신호에 따라 매매 실행
            if signals['action'] == 'BUY':
                self.order_handler.enter_long(symbol, signals['price'])
            elif signals['action'] == 'SELL':
                self.order_handler.enter_short(symbol, signals['price'])
            elif signals['action'] == 'EXIT':
                if position['position_amount'] > 0:
                    self.order_handler.exit_long(symbol, signals['price'])
                elif position['position_amount'] < 0:
                    self.order_handler.exit_short(symbol, signals['price'])


    # 기존 position_check 기능 유지
    def check_positions(self):
        for symbol in COIN_LIST:
            self.data_handler.position_data_update(symbol)
            self.order_handler.set_leverage(symbol)

    # 기존 balance check 로직 유지
    def check_balance(self):
        balance = self.data_handler.balance_data_update()
        log_balance(f"잔고 정보: {balance}")        # ... [기존 잔고 처리 로직] ...

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()