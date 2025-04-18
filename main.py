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
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация Flask
app = Flask(__name__)

@app.route('/')
def health_check():
    return "KosiTrade Operational", 200

# Конфигурация
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Валидация конфигурации
if not TOKEN or not CHAT_ID:
    logger.error("❌ Missing BOT_TOKEN or CHAT_ID in environment variables")
    raise RuntimeError("Required environment variables are missing")

# Инициализация бота Telegram
try:
    bot = Bot(token=TOKEN)
except TelegramError as e:
    logger.error(f"❌ Failed to initialize Telegram bot: {e}")
    raise

# Список отслеживаемых символов
SYMBOLS = [
    "FLOKIUSDT", "DOGEUSDT", "PEPEUSDT", "SHIBUSDT",
    "1000BONKUSDT", "WIFUSDT", "1000SATSUSDT",
    "1000RATSUSDT", "1000BENJIUSDT"
]

def fetch_candle_data(symbol):
    """Получение и обработка данных свечей с Binance API"""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=100"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        if not isinstance(data, list) or len(data) < 100:
            raise ValueError(f"Invalid response format for {symbol}")
            
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        return df.dropna()
        
    except Exception as e:
        logger.error(f"🚨 Error fetching data for {symbol}: {e}")
        raise

def analyze_market(df):
    """Анализ рыночных данных с использованием технических индикаторов"""
    try:
        # Расчет индикаторов
        df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
        df['ema20'] = ta.trend.EMAIndicator(df['close'], 20).ema_indicator()
        df['macd'] = ta.trend.MACD(df['close']).macd_diff()
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close']
        ).average_true_range()

        latest = df.iloc[-1]
        
        # Система оценки сигналов
        score = sum([
            latest['rsi'] < 35,  # Более гибкий порог
            latest['close'] > latest['ema20'],
            latest['macd'] > latest['macd'].shift(1),
            latest['volume'] > df['volume'].rolling(20).mean().iloc[-1] * 1.5
        ])
        
        return score, round(latest['close'], 6)
        
    except Exception as e:
        logger.error(f"🔧 Analysis error: {e}")
        return 0, 0.0

def send_telegram_alert(symbol, score, price):
    """Отправка сигнала в Telegram"""
    try:
        message = (
            f"🚨 **KosiTrade Signal**\n"
            f"▫️ *Asset*: `{symbol}`\n"
            f"▫️ *Signal Strength*: {score}/4\n"
            f"▫️ *Price*: ${price}\n"
            f"▫️ *Time*: {time.strftime('%H:%M:%S %Z')}"
        )
        bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode='Markdown'
        )
        logger.info(f"✅ Signal sent for {symbol}")
    except TelegramError as e:
        logger.error(f"📡 Telegram API Error: {e}")

def trading_engine():
    """Основной торговый цикл"""
    logger.info("🚀 Starting trading engine")
    
    try:
        bot.send_message(
            chat_id=CHAT_ID,
            text="✅ *KosiTrade Activated*\n_System is now monitoring markets_",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"⚠️ Failed to send startup message: {e}")

    while True:
        try:
            for symbol in SYMBOLS:
                try:
                    df = fetch_candle_data(symbol)
                    score, price = analyze_market(df)
                    
                    if score >= 3:
                        send_telegram_alert(symbol, score, price)
                        time.sleep(2)  # Anti-spam delay
                        
                except Exception as e:
                    logger.error(f"🔁 Error processing {symbol}: {e}")
                    continue
                    
            time.sleep(300)  # Интервал проверки
                
        except KeyboardInterrupt:
            logger.info("🛑 Manual shutdown requested")
            break
        except Exception as e:
            logger.error(f"💥 Critical error: {e}")
            time.sleep(60)

def start_server():
    """Запуск Flask сервера"""
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    # Запуск в отдельных потоках
    engine_thread = threading.Thread(target=trading_engine, daemon=True)
    server_thread = threading.Thread(target=start_server, daemon=True)
    
    try:
        engine_thread.start()
        server_thread.start()
        
        # Поддержка главного потока
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
    finally:
        engine_thread.join()
        server_thread.join()
