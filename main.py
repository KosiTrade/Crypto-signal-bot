import os
import time
import threading
import logging
import requests
import pandas as pd
import ta
import ccxt  # Исправлено с coxt на ccxt
from telegram import Bot
from flask import Flask

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

# Проверка переменных окружения
if not TOKEN or not CHAT_ID:
    logger.error("❌ BOT_TOKEN или CHAT_ID не установлены!")
    raise ValueError("Требуются переменные окружения")

# Инициализация бота Telegram
try:
    bot = Bot(token=TOKEN)
except Exception as e:
    logger.error(f"❌ Ошибка Telegram: {e}")
    raise

# Актуальные символы (проверены на Binance)
SYMBOLS = [
    "FLOKIUSDT", "DOGEUSDT", "PEPEUSDT",
    "SHIBUSDT", "1000BONKUSDT", "WIFUSDT",
    "1000SATSUSDT"  # Убраны несуществующие тикеры
]

def fetch_candle_data(symbol):
    """Получение данных с Binance API"""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=100"
    
    try:
        # Добавлены заголовки для обхода ошибки 451
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "X-MBX-APIKEY": os.getenv("BINANCE_API_KEY", "")
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        if not isinstance(data, list):
            raise ValueError("Некорректный ответ API")
            
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        return df.dropna()
        
    except Exception as e:
        logger.error(f"🚨 Ошибка получения данных: {str(e)[:100]}...")
        return None

def analyze_market(df):
    """Анализ рыночных данных"""
    if df is None or df.empty:
        return 0, 0.0
        
    try:
        df['rsi'] = ta.momentum.RSIIndicator(df['close']).rsi()
        df['ema20'] = ta.trend.EMAIndicator(df['close'], 20).ema_indicator()
        df['macd'] = ta.trend.MACD(df['close']).macd_diff()
        
        latest = df.iloc[-1]
        score = sum([
            latest['rsi'] < 35,
            latest['close'] > latest['ema20'],
            latest['macd'] > latest['macd'].shift(1),
            latest['volume'] > df['volume'].rolling(20).mean().iloc[-1] * 1.2
        ])
        
        return score, round(latest['close'], 6)
        
    except Exception as e:
        logger.error(f"🔧 Ошибка анализа: {e}")
        return 0, 0.0

def send_alert(symbol, score, price):
    """Отправка сигнала в Telegram"""
    try:
        message = (
            f"🚀 **Сигнал KosiTrade**\n"
            f"▫️ Монета: {symbol}\n"
            f"▫️ Сила сигнала: {score}/4\n"
            f"▫️ Цена: ${price}\n"
            f"▫️ Время: {time.strftime('%H:%M:%S %d.%m.%Y')}"
        )
        bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode='Markdown'
        )
        time.sleep(1)  # Защита от спама
    except Exception as e:
        logger.error(f"📡 Ошибка Telegram: {e}")

def trading_engine():
    """Основной торговый цикл"""
    logger.info("Запуск торгового движка")
    
    try:
        bot.send_message(CHAT_ID, "✅ Бот активирован")
    except Exception as e:
        logger.error(f"Ошибка стартового сообщения: {e}")

    while True:
        try:
            for symbol in SYMBOLS:
                try:
                    df = fetch_candle_data(symbol)
                    if df is None:
                        continue
                        
                    score, price = analyze_market(df)
                    
                    if score >= 3:
                        send_alert(symbol, score, price)
                        
                except Exception as e:
                    logger.error(f"Ошибка обработки {symbol}: {e}")
                    
                time.sleep(2)  # Задержка между символами
                
            time.sleep(300)  # Основной интервал проверки
            
        except KeyboardInterrupt:
            logger.info("Остановка по запросу")
            break
        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            time.sleep(60)

if __name__ == '__main__':
    # Запуск в фоновом потоке
    threading.Thread(target=trading_engine, daemon=True).start()
    
    # Запуск Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
