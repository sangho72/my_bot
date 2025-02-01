import time
from datetime import datetime, timezone, timedelta
import hmac
import hashlib
import json
import requests
import threading 
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from config.settings import API_KEY, SECRET_KEY, COIN_LIST, DATA_DIR, BASE_URL
import numpy as np
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
class DataHandler:
    def __init__(self):
        self.client = Client(API_KEY, SECRET_KEY)
        self.lock = threading.Lock()  # lock 속성 추가
        self.coin_data = {symbol: {'1m': self.load_historical_data(symbol, interval='1m'),
                               '1h': self.load_historical_data(symbol, interval='1h')} 
                      for symbol in COIN_LIST}
        # self.coin_data = {symbol: {'1m': pd.DataFrame(), '1h': pd.DataFrame()} for symbol in COIN_LIST}  # 빈 DataFrame으로 초기화
        self.orderbook_data = {symbol: None for symbol in COIN_LIST}  # orderbook_data 추가
        self.position_data = {symbol: {} for symbol in COIN_LIST}
        self.balance_data = {"wallet": 0.0, "total": 0.0, "free": 0, "used": 0.0, "PNL": 0.0}
        os.makedirs(DATA_DIR, exist_ok=True)  # 데이터 디렉토리 생성

    def initialize_data(self):
        """웹소켓 시작 전 초기 데이터 로드"""
        for symbol in COIN_LIST:
            # 1분, 1시간 데이터 초기화
            self.coin_data[symbol]['1m'] = self.load_historical_data(symbol, interval='1m', save_to_file=True)
            self.coin_data[symbol]['1h'] = self.load_historical_data(symbol, interval='1h', save_to_file=True)

    def write_balance(self,binance_balance):
        with open("binance_balance.txt", "a") as fp :
            fp.write(binance_balance)
            fp.write('\n')

    def get_account_info(self):
        url = f"{BASE_URL}/fapi/v2/account"

        # 타임스탬프와 서명 생성
        timestamp = int(time.time() * 1000)
        query_string = f"timestamp={timestamp}"
        signature = hmac.new(
            SECRET_KEY.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # 요청 헤더 설정
        headers = {
            "X-MBX-APIKEY": API_KEY
        }

        # 요청 보내기
        response = requests.get(url, headers=headers, params={"timestamp": timestamp, "signature": signature})

        # 결과 반환
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.status_code, "message": response.text}

    def balance_data_update(self,event_reason=None):
        nowtime = datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')
        balance = self.get_account_info()
        # print(balance)
        total_wallet_balance = round(float(balance['totalWalletBalance']),3) # total wallet balance, only for USDT asset
        total_unrealized_profit = round(float(balance['totalUnrealizedProfit']),3)
        usdt_free = round(float(balance['availableBalance']),3) # usdt_free
        usdt_used = round(float(balance['totalInitialMargin']),3) # usdt_used
        usdt_total = round(float(balance['totalMarginBalance']),3) # usdt_total

        self.balance_data['wallet']=total_wallet_balance
        self.balance_data['total']=usdt_total
        self.balance_data['free']=usdt_free
        self.balance_data['used']=usdt_used
        self.balance_data['PNL']=total_unrealized_profit

        binance_balance = (
                        f"{nowtime}\t"
                        f"wallet: {total_wallet_balance}\t"
                        f"total: {usdt_total}\t"
                        f"free: {usdt_free}\t"
                        f"used: {usdt_used}\t"
                        f"PNL: {total_unrealized_profit}"
                        )
        # event_reason이 전달된 경우, 추가
        if event_reason:
            binance_balance += f"\t{event_reason}"
        print(binance_balance)
        self.write_balance(binance_balance) # write balance to file
        return self.balance_data

    def position_data_update(self,symbol):
        url = f"{BASE_URL}/fapi/v2/positionRisk"

        # 타임스탬프와 서명 생성
        timestamp = int(time.time() * 1000)
        query_string = f"symbol={symbol}&timestamp={timestamp}"
        signature = hmac.new(
            SECRET_KEY.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # 요청 헤더 설정
        headers = {
            "X-MBX-APIKEY": API_KEY
        }

        # 요청 보내기
        response = requests.get(url, headers=headers, params={"symbol": symbol, "timestamp": timestamp, "signature": signature})

        # 결과 반환
        if response.status_code == 200:
            data = response.json()
            if data:
                self.position_data[symbol] = {
                    "avg_price": float(data[0]['entryPrice']),
                    "position_amount": float(data[0]['positionAmt']),
                    "leverage": int(data[0]['leverage']),
                    "unrealizedProfit": float(data[0]['unRealizedProfit']),
                    "breakeven_price": float(data[0]['breakEvenPrice'])
                }
                print(symbol,self.position_data[symbol])
                return self.position_data[symbol]
        else:
            print(f"Error fetching leverage for {symbol}: {response.text}")

    def save_orderbook_data(self, symbol):
        """오더북 데이터 저장"""
        path = os.path.join(DATA_DIR, f"orderbook_{symbol}.csv")
        df = pd.DataFrame(self.orderbook_data[symbol])
        df.to_csv(path, index=False)


    def load_historical_data(self, symbol, interval, limit=999, save_to_file=True):
        """
        Binance API를 통해 과거 데이터를 로드하고, 필요시 파일로 저장합니다.
        
        :param symbol: 코인 심볼 (예: 'BTCUSDT')
        :param interval: 데이터 간격 (예: '1m', '1h')
        :param limit: 가져올 데이터 개수
        :param save_to_file: 데이터를 파일로 저장할지 여부 (기본값: True)
        :return: pandas DataFrame
        """
        try:
            # Binance API를 통해 데이터 가져오기
            raw_data = self.client.futures_klines(
                symbol=symbol, 
                interval=interval, 
                limit=limit
            )
            
            # 데이터프레임으로 변환
            df = pd.DataFrame(raw_data, columns=[
                'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'Close time', 'Quote asset volume', 'Number of trades',
                'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
            ])
            
            # 필요한 컬럼만 선택 및 데이터 타입 변환
            df = df[['Open time', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df['Open time'] = pd.to_datetime(df['Open time'], unit='ms') + pd.Timedelta(hours=9)
            df['Open'] = df['Open'].astype(float)
            df['High'] = df['High'].astype(float)
            df['Low'] = df['Low'].astype(float)
            df['Close'] = df['Close'].astype(float)
            df['Volume'] = df['Volume'].astype(float)

            # self.add_indicators(df)  # 지표 추가
            # 파일로 저장 (옵션)
            if save_to_file:
                file_path = os.path.join(DATA_DIR, f"klines_{symbol}_{interval}.csv")
                df.to_csv(file_path, index=False, sep='\t')
                print(f"📁 데이터 저장 완료: {file_path}")
            
            return df
        
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {e}")
            return pd.DataFrame()  # 빈 데이터프레임 반환

    # 기존 함수들 유지
    def add_indicators(self, df):
        close = df['Close'].astype(float)
        df['RSI_14'] = ta.rsi(close, length=14)
        df['RSI_14'] = round(ta.rsi(close, length=14), 4)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        df['MACD'] = ema12 - ema26
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        return df

    # def update_positions(self, symbol):
    #     position = self.client.futures_position_information(symbol=symbol)[0]
    #     self.position_data[symbol] = {
    #         'avg_price': float(position['entryPrice']),
    #         'amount': float(position['positionAmt']),
    #         'leverage': int(position['leverage']),
    #         'unrealizedProfit': float(position['unRealizedProfit'])
    #     }
    #     print(f"📊 포지션 정보 갱신: {self.position_data[symbol]}")
# DataHandler.load_historical_data('XLMUSDT')
# data_handler = DataHandler()
# print(COIN_LIST)
# data_handler.initialize_data()
# data_handler.balance_data_update()
# data_handler.load_historical_data('ADAUSDT', interval='1m', save_to_file=True)