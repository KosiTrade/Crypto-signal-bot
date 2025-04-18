import os
import time
import threading
import logging
import requests
import pandas as pd
import ta
from flask import Flask
from telegram import Bot, TelegramError

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(name)

# Инициализация Flask
app = Flask(name)

@app.route('/')
def index():
    return "KosiTrade успешно работает"

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SYMBOLS = [
    "FLOKIUSDT", "DOGEUSDT", "PEPEUSDT", "SHIBUSDT",
    "1000BONKUSDT", "WIFUSDT", "1000SATSUSDT",
    "1000RATSUSDT", "1000BENJIUSDT"
]

# Проверка переменных окружения
if not TOKEN or not CHAT_ID:
    raise ValueError("Не заданы BOT_TOKEN или CHAT_ID в переменных окружения")

# Инициализация бота
bot = Bot(token=TOKEN)

def get_data(symbol):
    """Получение и обработка данных с Binance API"""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=100"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not isinstance(data, list):
            raise ValueError(f"Некорректный ответ API для {symbol}")
            
        df = pd.DataFrame(data, columns=[
            'time', 'open', 'high', 'low', 'close', 'volume',
            '_', '_', '_', '_', '_', '_'
        ])
        
        # Конвертация типов данных
        numeric_cols = ['close', 'high', 'low', 'volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        return df
    
    except Exception as e:
        logger.error(f"Ошибка при получении данных для {symbol}: {e}")
        raise

def analyze(df):
    """Анализ технических индикаторов"""
    try:
        df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
        df['ema20'] = ta.trend.EMAIndicator(df['close'], window=20).ema_indicator()
        df['macd'] = ta.trend.MACD(df['close']).macd_diff()
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high'], 
            low=df['low'], 
            close=df['close']
        ).average_true_range()

        latest = df.iloc[-1]
        score = 0

        # Система оценки сигналов
        conditions = [
            latest['rsi'] < 30,
            latest['close'] > latest['ema20'],
            latest['macd'] > 0,
            latest['volume'] > df['volume'].rolling(20).mean().iloc[-1]
        ]
        
        score = sum(conditions)
        return score, round(latest['close'], 6)
    
    except Exception as e:
        logger.error(f"Ошибка анализа данных: {e}")
        raise

def send_alert(symbol, score, price):
    """Отправка сообщения в Telegram"""
    try:
        message = (
            f"🚀 KosiTrade Signal\n"
            f"Coin: {symbol}\n"
            f"Score: {score}/4\n"
            f"Price: {price}\n"
            f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        bot.send_message(chat_id=CHAT_ID, text=message)
        logger.info(f"Signal sent for {symbol}")
    except TelegramError as e:
        logger.error(f"Telegram error: {e}")

def trading_cycle():
    """Основной торговый цикл"""
    logger.info("Starting trading cycle")
    try:
        bot.send_message(chat_id=CHAT_ID, text="✅ KosiTrade успешно запущен")
    except TelegramError as e:
        logger.error(f"Не удалось отправить стартовое сообщение: {e}")

    while True:
        try:
            for symbol in SYMBOLS:
                try:
                    df = get_data(symbol)
                    score, price = analyze(df)
                    
                    if score >= 3:
                        send_alert(symbol, score, price)
                        
                except Exception as e:
                    logger.error(f"Ошибка обработки {symbol}: {e}")
