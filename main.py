import os
import time
import logging
import numpy as np
import pandas as pd
import requests
import ccxt  # Универсальный API для бирж
import talib as ta
from sklearn.ensemble import RandomForestClassifier
from telegram import Bot, Update
from flask import Flask, request
from tradingview_ta import TA_Handler

# Конфигурация
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Инициализация компонентов
exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_SECRET'),
    'enableRateLimit': True
})

bot = Bot(token=os.getenv("BOT_TOKEN"))
model = RandomForestClassifier(n_estimators=100)

# 1. Machine Learning Model
def train_model():
    data = pd.read_csv('historical_data.csv')
    features = data[['RSI', 'MACD', 'Volume_Change']]
    target = data['Target']
    model.fit(features, target)

# 2. TradingView Integration
def get_tradingview_signal(symbol):
    analysis = TA_Handler(
        symbol=symbol,
        screener="crypto",
        exchange="BINANCE",
        interval="5m"
    )
    return analysis.get_analysis().summary

# 3. Risk Management System
def calculate_position_size(balance, risk_percent):
    return (balance * risk_percent) / 100

# 4. Advanced Technical Analysis
def calculate_indicators(df):
    df['RSI'] = ta.RSI(df['close'])
    df['MACD'] = ta.MACD(df['close']).macd
    df['ATR'] = ta.ATR(df['high'], df['low'], df['close'])
    df['Ichomoku'] = ta.ICHIMOKU(df['high'], df['low'], df['close']).ichimoku_9
    return df

# 5. Trading Strategy Core
def generate_signal(df):
    ml_prediction = model.predict([[df['RSI'].iloc[-1], df['MACD'].iloc[-1], df['Volume'].pct_change().iloc[-1]]])
    tv_signal = get_tradingview_signal('BTCUSDT')
    
    conditions = {
        'ml_buy': ml_prediction[0] == 1,
        'tv_buy': tv_signal['RECOMMENDATION'] == 'STRONG_BUY',
        'rsi_oversold': df['RSI'].iloc[-1] < 30,
        'macd_cross': df['MACD'].iloc[-1] > df['MACD'].iloc[-2]
    }
    
    if sum(conditions.values()) >= 3:
        return {
            'signal': 'BUY',
            'tp': df['close'].iloc[-1] * 1.03,  # 3% take profit
            'sl': df['close'].iloc[-1] * 0.98   # 2% stop loss
        }
    return {'signal': 'HOLD'}

# 6. Execution Engine
def execute_trade(signal):
    if signal['signal'] == 'BUY':
        balance = exchange.fetch_balance()['free']['USDT']
        size = calculate_position_size(balance, 2)  # 2% risk
        order = exchange.create_market_order(
            symbol='BTC/USDT',
            side='buy',
            amount=size,
            params={
                'stopLoss': {
                    'type': 'stopMarket',
                    'stopPrice': signal['sl']
                },
                'takeProfit': {
                    'type': 'takeProfitMarket',
                    'stopPrice': signal['tp']
                }
            }
        )
        return order

# 7. Telegram Notifications
def send_alert(signal):
    message = f"""
    🚀 **AI Trading Signal**
    - Signal: {signal['signal']}
    - Entry: {signal.get('price', 'N/A')}
    - Take Profit: {signal.get('tp', 'N/A')}
    - Stop Loss: {signal.get('sl', 'N/A')}
    - Confidence: {signal.get('confidence', 'High')}
    """
    bot.send_message(chat_id=os.getenv("CHAT_ID"), text=message, parse_mode='Markdown')

# Main Loop
def trading_loop():
    train_model()
    while True:
        try:
            data = exchange.fetch_ohlcv('BTC/USDT', '5m', limit=100)
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = calculate_indicators(df)
            signal = generate_signal(df)
            
            if signal['signal'] != 'HOLD':
                execute_trade(signal)
                send_alert(signal)
                
            time.sleep(300)
            
        except Exception as e:
            logger.error(f"Critical error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    threading.Thread(target=trading_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=10000)
