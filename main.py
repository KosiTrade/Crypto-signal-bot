import os
import time
import threading
import logging
import requests
import pandas as pd
import ta
from flask import Flask
from telegram import Bot, TelegramError

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- FLASK ---
app = Flask(__name__)

@app.route('/')
def health_check():
    return "KosiTrade V7 is running", 200

# --- НАСТРОЙКИ ---
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN or not CHAT_ID:
    logger.error("❌ BOT_TOKEN или CHAT_ID не установлены в переменных окружения")
    raise RuntimeError("Missing BOT_TOKEN or CHAT_ID")

bot = Bot(token=TOKEN)

# --- МОНИТОРИМЫЕ МОНЕТЫ ---
SYMBOLS = [
    "FLOKIUSDT", "DOGEUSDT", "PEPEUSDT", "SHIBUSDT",
    "1000BONKUSDT", "WIFUSDT", "1000SATSUSDT",
    "1000RATSUSDT", "1000BENJIUSDT"
]

BLACKLIST = set()  # сюда можно добавлять плохие монеты

# --- ФУНКЦИИ ---
def fetch_data(symbol):
    url = f"https://api4.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=100"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.dropna()
    except Exception as e:
        logger.error(f"🚨 Ошибка получения данных для {symbol}: {e}")
        raise

def analyze(df):
    try:
        df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
        df['ema20'] = ta.trend.EMAIndicator(df['close'], 20).ema_indicator()
        df['ema50'] = ta.trend.EMAIndicator(df['close'], 50).ema_indicator()
        df['macd'] = ta.trend.MACD(df['close']).macd_diff()
        df['atr'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close']).average_true_range()
        df['momentum'] = ta.momentum.ROCIndicator(df['close']).roc()

        latest = df.iloc[-1]
        score = sum([
            latest['rsi'] < 35,
            latest['close'] > latest['ema20'] and latest['ema20'] > latest['ema50'],
            latest['macd'] > 0 and latest['macd'] > df['macd'].iloc[-2],
            latest['volume'] > df['volume'].rolling(20).mean().iloc[-1] * 1.5,
            latest['momentum'] > 0
        ])
        return score, round(latest['close'], 6)
    except Exception as e:
        logger.error(f"🔧 Ошибка анализа данных: {e}")
        return 0, 0

def send_signal(symbol, score, price):
    try:
        msg = (
            f"🚨 *KosiTrade V7 Signal*\n"
            f"`{symbol}` — Сила сигнала: *{score}/5*\n"
            f"Цена: ${price}\n"
            f"[Binance Chart](https://www.binance.com/en/trade/{symbol})"
        )
        bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown', disable_web_page_preview=True)
        logger.info(f"✅ Сигнал отправлен: {symbol}")
    except TelegramError as e:
        logger.error(f"📡 Ошибка Telegram: {e}")

def trading_loop():
    logger.info("🚀 KosiTrade V7 начал работу")
    bot.send_message(chat_id=CHAT_ID, text="✅ *KosiTrade V7 активирован*", parse_mode='Markdown')
    while True:
        for symbol in SYMBOLS:
            if symbol in BLACKLIST:
                continue
            try:
                df = fetch_data(symbol)
                score, price = analyze(df)
                if score >= 4:
                    send_signal(symbol, score, price)
                    time.sleep(2)
            except Exception:
                continue
        time.sleep(300)

def start_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- ЗАПУСК ---
if __name__ == '__main__':
    threading.Thread(target=trading_loop, daemon=True).start()
    threading.Thread(target=start_server, daemon=True).start()
    while True:
        time.sleep(1)
