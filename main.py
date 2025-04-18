import os
import time
import requests
from telegram import Bot
import ta
import pandas as pd

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
bot = Bot(token=TOKEN)

SYMBOLS = ["FLOKIUSDT", "DOGEUSDT", "PEPEUSDT", "SHIBUSDT", "1000BONKUSDT", "WIFUSDT", "1000SATSUSDT", "1000RATSUSDT", "1000BENJIUSDT", "DEGENUSDT"]

def get_klines(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=100"
        response = requests.get(url)
        data = response.json()
        if not isinstance(data, list) or len(data) < 30:
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
        bot.send_message(chat_id=CHAT_ID, text=f"❌ Ошибка при получении {symbol}: {e}")
        return None

def analyze(df):
    try:
        close = df["close"]
        volume = df["volume"]
        df["rsi"] = ta.momentum.RSIIndicator(close).rsi()
        df["ema20"] = ta.trend.EMAIndicator(close, window=20).ema_indicator()
        df["macd"] = ta.trend.MACD(close).macd_diff()
        df["atr"] = ta.volatility.AverageTrueRange(high=df["high"],
                                                   low=df["low"],
                                                   close=close).average_true_range()

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

        return signal_score
    except Exception as e:
        bot.send_message(chat_id=CHAT_ID, text=f"❌ Ошибка в анализе: {e}")
        return None

def send_signal(symbol, score, price):
    msg = f"KosiTrade сигнал!\nМонета: {symbol}\nСигнал: {score}/4\nЦена: {price}\nВремя: {time.strftime('%H:%M:%S')}"
    bot.send_message(chat_id=CHAT_ID, text=msg)

bot.send_message(chat_id=CHAT_ID, text="✅ KosiTrade V6 запущен")

while True:
    try:
        for symbol in SYMBOLS:
            df = get_klines(symbol)
            if df is None:
                continue
            score = analyze(df)
            if score is None:
                continue
            price = df["close"].iloc[-1]
            if score >= 3:
                send_signal(symbol, score, price)
        time.sleep(300)
    except Exception as e:
        bot.send_message(chat_id=CHAT_ID, text=f"❌ Общая ошибка: {e}")
        time.sleep(60)
