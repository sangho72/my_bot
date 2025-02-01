import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class BasicStrategy:
    def __init__(self):
        self.trade_history = []  # 거래 내역 저장

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        종합적 기술 지표 계산
        :param df: OHLCV 데이터프레임
        :return: 지표가 추가된 데이터프레임
        """
        # 이동평균선
        df['ema_200'] = round(ta.ema(df['Close'], length=200),4)
        df['ema_50'] = round(ta.ema(df['Close'], length=50),4)
        
        # 모멘텀 지표
        df['rsi'] = round(ta.rsi(df['Close'], length=14),4)
        stoch = ta.stoch(df['High'], df['Low'], df['Close'])
        df = pd.concat([df, stoch], axis=1)
        
        # 추세 지표
        adx = ta.adx(df['High'], df['Low'], df['Close'])
        df = pd.concat([df, adx], axis=1)
        
        # 변동성 지표
        df['atr'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        
        # MACD
        macd = ta.macd(df['Close'])
        df = pd.concat([df, macd], axis=1)
        
        # 피보나치 되돌림 레벨
        recent_high = df['High'].rolling(50).max()
        recent_low = df['Low'].rolling(50).min()
        df['fib_0.236'] = recent_high - (recent_high - recent_low) * 0.236
        df['fib_0.5'] = recent_high - (recent_high - recent_low) * 0.5
        df['fib_0.786'] = recent_high - (recent_high - recent_low) * 0.786
        
        return df.dropna()

    def generate_trading_signals(self, df: pd.DataFrame, position: Dict) -> Dict:
        """
        다중 조건 기반 매매 신호 생성
        :param df: 지표가 포함된 데이터프레임
        :param position: 현재 포지션 정보
        :return: 매매 신호 (action, price, reason)
        """
        # signals = {'action': 'HOLD', 'price': None, 'reason': None}
        latest = df.iloc[-1]
        signals = {'action': 'HOLD', 'price': latest['Close'], 'reason': None}

        # 상승 추세 조건
        bull_condition = (
            latest['Close'] > latest['ema_200'] and
            latest['ADX_14'] > 25 and
            latest['MACD_12_26_9'] > latest['MACDs_12_26_9']
        )
        
        # 하락 추세 조건
        bear_condition = (
            latest['Close'] < latest['ema_200'] and
            latest['ADX_14'] > 25 and
            latest['MACD_12_26_9'] < latest['MACDs_12_26_9']
        )

        # 매수 신호 (3단계 확인)
        if bull_condition and self._confirm_long_entry(df):
            signals.update({
                'action': 'BUY',
                'price': latest['Close'],
                'reason': f"EMA200 상승돌파 | RSI:{latest['rsi']:.1f} | MACD 양수확대"
            })
        
        # 매도 신호 (3단계 확인)
        elif bear_condition and self._confirm_short_entry(df):
            signals.update({
                'action': 'SELL',
                'price': latest['Close'],
                'reason': f"EMA200 하락이탈 | RSI:{latest['rsi']:.1f} | MACD 음수확대"
            })
        
        # 청산 신호 (동적 익절/손절)
        elif position['position_amount'] != 0:
            signals.update(self._check_exit_conditions(df, position))
        
        return signals

    def _confirm_long_entry(self, df: pd.DataFrame) -> bool:
        """매수 신호 2차 확인"""
        latest = df.iloc[-1]
        return (
            latest['Volume'] > df['Volume'].rolling(20).mean().iloc[-1] and
            latest['Close'] > latest['fib_0.5'] and
            latest['STOCHk_14_3_3'] > latest['STOCHd_14_3_3']
        )

    def _confirm_short_entry(self, df: pd.DataFrame) -> bool:
        """매도 신호 2차 확인"""
        latest = df.iloc[-1]
        return (
            latest['Volume'] > df['Volume'].rolling(20).mean().iloc[-1] and
            latest['Close'] < latest['fib_0.5'] and
            latest['STOCHk_14_3_3'] < latest['STOCHd_14_3_3']
        )

    def _check_exit_conditions(self, df: pd.DataFrame, position: Dict) -> Dict:
        """동적 청산 조건 계산"""
        current_price = df['Close'].iloc[-1]
        entry_price = position['avg_price']
        position_type = 'LONG' if position['position_amount'] > 0 else 'SHORT'
        
        # 변동성 기반 손절매 계산
        atr = df['atr'].iloc[-1]
        dynamic_stop_loss = current_price - (2 * atr) if position_type == 'LONG' else current_price + (2 * atr)
        
        # 시간 기반 청산 조건 (최대 24시간 보유)
        time_in_position = pd.Timestamp.now() - position['entry_time']
        
        exit_condition = {
            'action': 'EXIT',
            'price': dynamic_stop_loss,
            'reason': f"동적 손절매 | 현재가: {current_price} | 진입가: {entry_price}"
        }
        
        if time_in_position > timedelta(hours=24):
            exit_condition['reason'] = "최대 보유 시간 초과"
        
        return exit_condition

    def performance_metrics(self) -> Dict:
        """전략 성과 분석"""
        if not self.trade_history:
            return {}
        
        win_trades = [t for t in self.trade_history if t['profit'] > 0]
        loss_trades = [t for t in self.trade_history if t['profit'] <= 0]
        
        return {
            'total_trades': len(self.trade_history),
            'win_rate': len(win_trades) / len(self.trade_history) if self.trade_history else 0,
            'profit_factor': sum(t['profit'] for t in win_trades) / abs(sum(t['profit'] for t in loss_trades)) if loss_trades else float('inf'),
            'max_drawdown': self._calculate_drawdown(),
            'sharpe_ratio': self._calculate_sharpe()
        }

    def _calculate_drawdown(self) -> float:
        """최대 낙폭 계산"""
        equity_curve = np.cumsum([t['profit'] for t in self.trade_history])
        max_drawdown = (np.maximum.accumulate(equity_curve) - equity_curve).max()
        return float(max_drawdown)

    def _calculate_sharpe(self) -> float:
        """샤프 지수 계산"""
        returns = np.array([t['profit'] for t in self.trade_history])
        if len(returns) < 2:
            return 0.0
        return float(np.mean(returns) / np.std(returns) * np.sqrt(365))