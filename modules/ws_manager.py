import os
import time
import pandas as pd
import websocket
import json
import threading
from config.settings import COIN_LIST, API_KEY , DATA_DIR
from modules.data_handler import DataHandler
from utils.logger import logger

class WebSocketManager:
    def __init__(self, data_handler: DataHandler):
        self.data_handler = data_handler
        self.ws_connections = []
        self.stop_event = threading.Event()
        
        # 계정 업데이트 웹소켓 별도 관리
        self.account_ws = None

    def _start_single_websocket(self, url, on_message):
        """개별 웹소켓 연결 관리"""
        def run():
            while not self.stop_event.is_set():
                try:
                    ws = websocket.WebSocketApp(
                        url,
                        on_message=on_message,
                        on_error=self.on_error,
                        on_close=self.on_close
                    )
                    ws.run_forever()
                except Exception as e:
                    logger.error(f"웹소켓 연결 실패: {e}")
                time.sleep(5)  # 재연결 대기

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    # 기존 on_message_account_update 로직 완전 재현
    def _on_account_update(self, ws, message):
        data = json.loads(message)
        event_type = data.get('e')
        
        if event_type == 'ACCOUNT_UPDATE':
            positions = data['a']['P']
            for pos in positions:
                symbol = pos['s']
                self.data_handler.position_data[symbol] = {
                    'avg_price': float(pos['ep']),
                    'position_amount': float(pos['pa']),
                    'leverage': int(pos['l']),
                    'unrealizedProfit': float(pos['up'])
                }
            logger.info("포지션 업데이트 완료")

    # 기존 on_message_orderbook 로직 재현
    def _on_orderbook(self, ws, message):
        data = json.loads(message)
        symbol = data['s']
        with self.data_handler.lock:
            self.data_handler.orderbook_data[symbol] = data
            self.data_handler.save_orderbook_data(symbol)

    # 기존 on_message_1m/1h 캔들 처리 재현
    def _on_kline(self, ws, message, timeframe, save_to_file=True):
        data = json.loads(message)
        kline = data['k']
        symbol = data['s']
        # open_time = pd.to_datetime(candle['t'], unit='ms') + pd.Timedelta(hours=9)  # UTC+9로 변환
        # open_time_str = open_time.strftime('%Y-%m-%d %H:%M')  # 형식 변환

        with self.data_handler.lock:
            if self.data_handler.coin_data[symbol][timeframe].empty:
                self.data_handler.coin_data[symbol][timeframe] = pd.DataFrame(columns=[
                    'Open time', 'Open', 'High', 'Low', 'Close', 'Volume'
                ])
                
            df = self.data_handler.coin_data[symbol][timeframe]

            # 신규 데이터 생성
            new_row = {
                'Open time': pd.to_datetime(kline['t'], unit='ms') + pd.Timedelta(hours=9),
                'Open': float(kline['o']),
                'High': float(kline['h']),
                'Low': float(kline['l']),
                'Close': float(kline['c']),
                'Volume': float(kline['v'])
            }
            
            # 데이터 업데이트
            if kline['x']:  # 캔들 종료
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                if len(df) > 1000:
                    df = df.iloc[1:]  # 80개의 최신 데이터 유지

            else:  # 캔들 업데이트
                # if not df.empty:
                #     df.iloc[-1] = list(new_row.values())
                # 캔들 진행 중: OHLCV만 업데이트
                if not df.empty:
                    df.loc[df.index[-1], ['Open', 'High', 'Low', 'Close', 'Volume']] = [
                        new_row['Open'], new_row['High'], new_row['Low'], 
                        new_row['Close'], new_row['Volume']
                    ]
 
            self.data_handler.coin_data[symbol][timeframe] = df

            # 파일로 저장 (옵션)
            if save_to_file:
                file_path = os.path.join(DATA_DIR, f"klines_{symbol}_{timeframe}.csv")
                df.to_csv(file_path, index=False, sep='\t')

    def start_account_websocket(self):
        """계정 업데이트 웹소켓 (기존 start_account_update_websocket 재현)"""
        listen_key = self.data_handler.client.futures_stream_get_listen_key()
        url = f"wss://fstream.binance.com/ws/{listen_key}"
        self.account_ws = self._start_single_websocket(url, self._on_account_update)

    def start_coin_websockets(self):
        """코인별 웹소켓 3개씩 생성 (기존 start_websocket 함수 재현)"""
        for symbol in COIN_LIST:
            symbol_lower = symbol.lower()
            
            # 1. 오더북 웹소켓
            self._start_single_websocket(
                f"wss://fstream.binance.com/ws/{symbol_lower}@depth20@500ms",
                self._on_orderbook
            )
            
            # 2. 1분 캔들 웹소켓
            self._start_single_websocket(
                f"wss://fstream.binance.com/ws/{symbol_lower}@kline_1m",
                lambda ws, msg: self._on_kline(ws, msg, '1m')
            )
            
            # 3. 1시간 캔들 웹소켓
            self._start_single_websocket(
                f"wss://fstream.binance.com/ws/{symbol_lower}@kline_1h",
                lambda ws, msg: self._on_kline(ws, msg, '1h')
            )

    def on_error(self, ws, error):
        logger.error(f"웹소켓 에러: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"웹소켓 연결 종료: {close_status_code} - {close_msg}")

    def stop_all(self):
        self.stop_event.set()
        if self.account_ws:
            self.account_ws.close()