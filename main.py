import os
import time
import threading
import requests
import pandas as pd
import ta
from flask import Flask
from telegram import Bot

# Flask-приложение
app = Flask(name)
@app.route('/')
def index():
    return "KosiTrade работает"

# Telegram токены
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
bot = Bot(token=TOKEN)

SYMBOLS = [
    "FLOKIUSDT", "DOGEUSDT", "PEPEUSDT", "SHIBUSDT",
    "1000BONKUSDT", "WIFUSDT", "1000SATSUSDT",
    "1000RATSUSDT", "1000BENJIUSDT"
]

def get_data(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=100"
    response = requests.get(url)
    data = response.json()
    df = pd.DataFrame(data, columns=[
        'time', 'open', 'high', 'low', 'close', 'volume',
        '_', '_', '_', '_', '_', '_'
    ])
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['volume'] = df['volume'].astype(float)
    return df

def analyze(df):
    df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
    df['ema'] = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator()
    df['macd'] = ta.trend.MACD(df['close']).macd_diff()
    df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close']).average_true_range()

    latest = df.iloc[-1]
    score = 0
    if latest['rsi'] < 30:
        score += 1
    if latest['close'] > latest['ema']:
        score += 1
    if latest['macd'] > 0:
        score += 1
    if latest['volume'] > df['volume'].rolling(20).mean().iloc[-1]:
        score += 1

    return score, latest['close']

def send_signal(symbol, score, price):
    message = f"KosiTrade сигнал!\nМонета: {symbol}\nСигнал: {score}/4\nЦена: {price}"
    bot.send_message(chat_id=CHAT_ID, text=message)

def bot_loop():
    bot.send_message(chat_id=CHAT_ID, text="✅ KosiTrade запущен")
    while True:
        try:
            for symbol in SYMBOLS:
                df = get_data(symbol)
                score, price = analyze(df)
                if score >= 3:
                    send_signal(symbol, score, price)
            time.sleep(300)
        except Exception as e:
            bot.send_message(chat_id=CHAT_ID, text=f"❌ Ошибка: {e}")
            time.sleep(60)

# Фоновый поток
threading.Thread(target=bot_loop).start()

# Запуск Flask
if name == 'main':
    app.run(host='0.0.0.0', port=10000)
