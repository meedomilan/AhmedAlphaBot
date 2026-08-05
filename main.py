import os
import asyncio
import logging
import time
import pandas as pd
from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException
from telegram import Bot
from dotenv import load_dotenv

# إعداد نظام التسجيل (Logging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# الإعدادات
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RVOL_THRESHOLD = 2.0  # تقليل العتبة للاكتشاف المبكر جداً
PRICE_CHANGE_THRESHOLD = 0.5  # 0.5% كافية لبدء التنبيه في البث الحي
MAX_SYMBOLS = 150  # زيادة العدد قليلاً مع مراعاة استقرار الـ IP

# بيانات العملات
coin_data = {}
last_alert_time = {}

async def send_telegram_alert(message):
    """إرسال فوري دون تأخير"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Telegram error: {e}")

def calculate_trade_details(symbol, current_price, direction):
    """حساب تفاصيل الصفقة (Entry, SL, TP)"""
    if direction == "LONG":
        entry = current_price
        sl = entry * 0.985  # وقف خسارة 1.5%
        tp1 = entry * 1.02   # هدف أول 2%
        tp2 = entry * 1.05   # هدف ثاني 5%
        return entry, sl, tp1, tp2
    else:
        entry = current_price
        sl = entry * 1.015  # وقف خسارة 1.5%
        tp1 = entry * 0.98   # هدف أول 2%
        tp2 = entry * 0.95   # هدف ثاني 5%
        return entry, sl, tp1, tp2

async def process_realtime_data(symbol, data):
    """معالجة البيانات اللحظية (دون انتظار إغلاق الشمعة)"""
    try:
        current_price = float(data['c'])
        current_volume = float(data['v'])
        
        if symbol not in coin_data:
            coin_data[symbol] = {'prices': [], 'volumes': []}
        
        # تخزين البيانات التاريخية (كل ثانية تصل بيانات جديدة)
        # سنقوم بتحديث البيانات التاريخية كل دقيقة في الخلفية، وهنا نستخدمها للمقارنة
        if not coin_data[symbol]['volumes']:
            return

        avg_vol = sum(coin_data[symbol]['volumes']) / len(coin_data[symbol]['volumes'])
        
        # حساب التغير السعري اللحظي مقارنة بآخر سعر مسجل
        last_price = coin_data[symbol]['prices'][-1] if coin_data[symbol]['prices'] else current_price
        price_change = ((current_price - last_price) / last_price) * 100
        
        rvol = current_volume / (avg_vol / 60) if avg_vol > 0 else 0 # تقدير الحجم اللحظي مقابل متوسط الدقيقة

        # تجنب تكرار التنبيهات لنفس العملة في وقت قصير (كل 5 دقائق تنبيه واحد)
        now = time.time()
        if symbol in last_alert_time and now - last_alert_time[symbol] < 300:
            return

        if rvol >= RVOL_THRESHOLD and abs(price_change) >= PRICE_CHANGE_THRESHOLD:
            direction = "LONG" if price_change > 0 else "SHORT"
            entry, sl, tp1, tp2 = calculate_trade_details(symbol, current_price, direction)
            
            icon = "🚀" if direction == "LONG" else "📉"
            msg = (
                f"{icon} *إشارة انفجار فوري (Real-time)!*\n\n"
                f"💎 *العملة:* `{symbol}`\n"
                f"📡 *الاتجاه:* `{direction}`\n"
                f"💵 *السعر الحالي:* `{current_price}`\n"
                f"🔥 *قوة الحجم (RVOL):* `{rvol:.2f}x`\n"
                f"⚡ *التغير اللحظي:* `{price_change:+.2f}%`\n\n"
                f"📝 *تفاصيل الصفقة المقترحة:*\n"
                f"🎯 *الدخول:* `{entry:.4f}`\n"
                f"🚫 *وقف الخسارة:* `{sl:.4f}`\n"
                f"✅ *الهدف 1:* `{tp1:.4f}`\n"
                f"✅ *الهدف 2:* `{tp2:.4f}`\n\n"
                f"🔗 [تداول الآن](https://www.binance.com/en/futures/{symbol})"
            )
            
            last_alert_time[symbol] = now
            logger.info(f"Instant Alert: {symbol} {direction}")
            await send_telegram_alert(msg)

    except Exception as e:
        logger.error(f"Processing error for {symbol}: {e}")

async def update_historical_data(client, symbols):
    """تحديث البيانات التاريخية في الخلفية كل 5 دقائق"""
    while True:
        try:
            for symbol in symbols:
                klines = await client.futures_klines(symbol=symbol, interval='1m', limit=20)
                coin_data[symbol] = {
                    'prices': [float(k[4]) for k in klines],
                    'volumes': [float(k[5]) for k in klines]
                }
                await asyncio.sleep(0.5) # تأخير بسيط لتجنب الحظر
            logger.info("Historical data updated.")
            await asyncio.sleep(300)
        except Exception as e:
            logger.error(f"History update error: {e}")
            await asyncio.sleep(60)

async def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.critical("Missing Telegram credentials.")
        return

    while True:
        client = await AsyncClient.create()
        try:
            logger.info("Connecting to Binance Futures...")
            exchange_info = await client.futures_exchange_info()
            all_symbols = [s['symbol'] for s in exchange_info['symbols'] 
                          if s['status'] == 'TRADING' and s['symbol'].endswith('USDT')]
            
            monitored_symbols = all_symbols[:MAX_SYMBOLS]
            
            # تشغيل تحديث البيانات التاريخية في الخلفية
            asyncio.create_task(update_historical_data(client, monitored_symbols))
            
            bm = BinanceSocketManager(client)
            # استخدام 'ticker' للحصول على تحديثات فورية كل ثانية بدلاً من kline_1m
            streams = [f"{s.lower()}@ticker" for s in monitored_symbols]
            
            async with bm.futures_multiplex_socket(streams) as ms:
                while True:
                    res = await ms.recv()
                    if res and 'data' in res:
                        await process_realtime_data(res['data']['s'], res['data'])
                            
        except BinanceAPIException as e:
            if e.code == -1003:
                logger.warning("IP Ban detected. Cooling down...")
                await asyncio.sleep(600)
            else:
                logger.error(f"Binance Error: {e}")
                await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Global Error: {e}")
            await asyncio.sleep(60)
        finally:
            await client.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
