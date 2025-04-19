import os
import logging
import requests
import pandas as pd
import ta
import time
from telegram import Bot
from telegram.error import TelegramError

# Настройка логов
logging.basicConfig(
    format="%(asctime)s - *main* - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Настройка Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
bot = Bot(token=BOT_TOKEN)

# Параметры Binance
BASE_URL = "https://api.binance.com"
SYMBOLS = ["FLOKIUSDT", "PEPEUSDT", "SHIBUSDT", "DOGEUSDT"]
INTERVAL = "5m"
LIMIT = 100

def fetch_klines(symbol):
    url = f"{BASE_URL}/api/v3/klines?symbol={symbol}&interval={INTERVAL}&limit={LIMIT}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["close"] = pd.to_numeric(df["close"])
        df["volume"] = pd.to_numeric(df["volume"])
        return df
    except Exception as e:
        logging.error(f"🚨 Error fetching data for {symbol}: {e}")
        return None

def analyze(df):
    df["rsi"] = ta.momentum.RSIIndicator(close=df["close"]).rsi()
    df["ema_20"] = ta.trend.EMAIndicator(close=df["close"], window=20).ema_indicator()
    df["macd"] = ta.trend.MACD(close=df["close"]).macd_diff()

    last = df.iloc[-1]
    signals = []

    if last["rsi"] < 30:
        signals.append("RSI < 30 (перепродан)")
    if last["close"] > last["ema_20"]:
        signals.append("Цена выше EMA20")
    if last["macd"] > 0:
        signals.append("MACD > 0")

    if len(signals) >= 2:
        return True, signals
    return False, signals

def send_signal(symbol, signals):
    try:
        message = f"📊 Сигнал для {symbol}\n" + "\n".join(f"• {s}" for s in signals)
        bot.send_message(chat_id=CHAT_ID, text=message)
        logging.info(f"✅ Сигнал отправлен для {symbol}")
    except TelegramError as e:
        logging.error(f"❌ Ошибка отправки Telegram: {e}")

def main():
    while True:
        for symbol in SYMBOLS:
            df = fetch_klines(symbol)
            if df is not None:
                try:
                    decision, signals = analyze(df)
                    if decision:
                        send_signal(symbol, signals)
                except Exception as e:
                    logging.error(f"🔁 Error processing {symbol}: {e}")
        time.sleep(300)  # 5 минут

if __name__ == "__main__":
    main()
