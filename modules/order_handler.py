from binance.client import Client
from binance.exceptions import BinanceAPIException
from decimal import Decimal
from config.settings import API_KEY, SECRET_KEY, TARGET_LEVERAGE, TRADE_RATE
from utils.logger import log_trade
import threading

class OrderHandler:
    def __init__(self, data_handler):
        self.client = Client(API_KEY, SECRET_KEY)
        self.data_handler = data_handler
        self.lock = threading.Lock()

    def set_leverage(self, symbol):
        """레버리지 설정 (기존 로직 유지)"""
        try:
            self.client.futures_change_leverage(
                symbol=symbol, 
                leverage=TARGET_LEVERAGE
            )
        except BinanceAPIException as e:
            print(f"{symbol} 레버리지 설정 실패: {e}")

    def cancel_all_orders(self, symbol):
        """모든 오더 취소 (기존 로직 유지)"""
        try:
            self.client.futures_cancel_all_open_orders(symbol=symbol)
            print(f"{symbol} 모든 오더 취소 완료")
        except BinanceAPIException as e:
            print(f"{symbol} 오더 취소 실패: {e}")

    def calculate_order_amount(self, symbol):
        """주문 금액 계산 (기존 트레이드 레이트 적용)"""
        balance = float(self.data_handler.balance_data['wallet'])
        price = self.data_handler.coin_data[symbol]['1m']['Close'].iloc[-1]
        return round((balance * TRADE_RATE * TARGET_LEVERAGE) / price, 4)

    def create_order(self, symbol, side, order_type, quantity, price=None, **kwargs):
        """기본 주문 생성 (기존 로직 확장)"""
        try:
            params = {
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'quantity': quantity,
                'timeInForce': 'GTC' if order_type == 'LIMIT' else None
            }
            if price: 
                params['price'] = str(Decimal(price).normalize())
            params.update(kwargs)
            
            order = self.client.futures_create_order(**params)
            log_trade(symbol, side, price or 'MARKET', quantity)
            return order
        except BinanceAPIException as e:
            print(f"{symbol} {side} 주문 실패: {e}")
            return None

    #▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
    # 기존 longstart/longend/shortstart/shortend 함수 리팩토링
    #▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

    def enter_long(self, symbol, coin_low):
        """롱 포지션 진입 (기존 longstart 함수 대체)"""
        with self.lock:
            position = self.data_handler.position_data[symbol]
            if position['position_amount'] == 0:
                qty = self.calculate_order_amount(symbol)
                return self.create_order(
                    symbol=symbol,
                    side='BUY',
                    order_type='LIMIT',
                    quantity=qty,
                    price=coin_low
                )

    def exit_long(self, symbol, coin_high):
        """롱 포지션 청산 (기존 longend 함수 대체)"""
        with self.lock:
            position = self.data_handler.position_data[symbol]
            if position['position_amount'] > 0:
                self.cancel_all_orders(symbol)
                return self.create_order(
                    symbol=symbol,
                    side='SELL',
                    order_type='LIMIT',
                    quantity=abs(position['position_amount']),
                    price=coin_high
                )

    def enter_short(self, symbol, coin_high):
        """숏 포지션 진입 (기존 shortstart 함수 대체)"""
        with self.lock:
            position = self.data_handler.position_data[symbol]
            if position['position_amount'] == 0:
                qty = self.calculate_order_amount(symbol)
                return self.create_order(
                    symbol=symbol,
                    side='SELL',
                    order_type='LIMIT',
                    quantity=qty,
                    price=coin_high
                )

    def exit_short(self, symbol, coin_low):
        """숏 포지션 청산 (기존 shortend 함수 대체)"""
        with self.lock:
            position = self.data_handler.position_data[symbol]
            if position['position_amount'] < 0:
                self.cancel_all_orders(symbol)
                return self.create_order(
                    symbol=symbol,
                    side='BUY',
                    order_type='LIMIT',
                    quantity=abs(position['position_amount']),
                    price=coin_low
                )

    def set_trailing_stop(self, symbol, activationPrice, callbackRate):
        """트레일링 스탑 오더 설정 (신규 추가)"""
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side='SELL' if self.data_handler.position_data[symbol]['position_amount'] > 0 else 'BUY',
                type='TRAILING_STOP_MARKET',
                activationPrice=activationPrice,
                callbackRate=callbackRate,
                quantity=abs(self.data_handler.position_data[symbol]['position_amount'])
            )
            print(f"{symbol} 트레일링 스탑 설정 완료: {order}")
            return order
        except BinanceAPIException as e:
            print(f"{symbol} 트레일링 스탑 설정 실패: {e}")
            return None
        
