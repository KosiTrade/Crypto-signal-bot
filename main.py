import os
import time
import requests
import pandas as pd
import ta
from telegram import Bot
from flask import Flask

# Flask для Render, чтобы не падал процесс
app = Flask(name)

# Telegram Bot
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
bot = Bot(token=TOKEN)

# Список монет
SYMBOLS = [
    "FLOKIUSDT", "DOGEUSDT", "PEPEUSDT", "SHIBUSDT", "1000BONKUSDT",
    "WIFUSDT", "1000SATSUSDT", "1000RATSUSDT", "1000BENJIUSDT"
]

def get_klines(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=100"
    try:
        response = requests.get(url)
        data = response.json()
        if not isinstance(data, list):
            raise ValueError(f"Недостаточно данных от Binance для {symbol}: {data}")
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "_", "_", "_", "_", "_", "_"
        ])
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        return df
    except Exception as e:
        raise RuntimeError(f"Ошибка при получении {symbol}: {e}")

def analyze(df):
    close = df["close"]
    volume = df["volume"]
    df["rsi"] = ta.momentum.RSIIndicator(close).rsi()
    df["ema20"] = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    df["macd"] = ta.trend.MACD(close).macd_diff()
    df["atr"] = ta.volatility.AverageTrueRange(
        high=df["high"], low=df["low"], close=close).average_true_range()

    latest = df.iloc[-1]
    signal_score = 0

    if latest["rsi"] < 30:
        signal_score += 1
    if latest["close"] > latest["ema20"]:
        signal_score += 1
    if latest["macd"] > 0:
        signal_score += 1
    if latest["volume"] > df["volume"].rolling(20).mean().iloc[-1]:
        signal_score += 1

    return signal_score, latest["close"]

def send_signal(symbol, score, price):
    msg = (
        f"KosiTrade сигнал!\n"
        f"Монета: {symbol}\n"
        f"Сигнал: {score}/4\n"
        f"Цена: {price}\n"
        f"Время: {time.strftime('%H:%M:%S')}"
    )
    bot.send_message(chat_id=CHAT_ID, text=msg)

# Стартовое сообщение
bot.send_message(chat_id=CHAT_ID, text="✅ KosiTrade V6 запущен")

# Главный цикл
while True:
    try:
        for symbol in SYMBOLS:
            try:
                df = get_klines(symbol)
                score, price = analyze(df)
                if score >= 3:
                    send_signal(symbol, score, price)
            except Exception as e:
                bot.send_message(chat_id=CHAT_ID, text=f"⚠️ {e}")
        time.sleep(300)  # Ждём 5 минут
    except Exception as e:
        bot.send_message(chat_id=CHAT_ID, text=f"❌ Главная ошибка: {e}")
        time.sleep(60)
