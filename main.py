import os
import asyncio
import logging
import pandas as pd
from binance import AsyncClient, BinanceSocketManager
from telegram import Bot
from dotenv import load_dotenv

# إعداد نظام التسجيل (Logging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# تحميل المتغيرات البيئية
load_dotenv()

# الإعدادات المحدثة (أقل صرامة)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
RVOL_THRESHOLD = 2.5  # حجم تداول 2.5 أضعاف المتوسط (بدلاً من 5)
PRICE_CHANGE_THRESHOLD = 0.8  # ارتفاع 0.8% في دقيقة واحدة (بدلاً من 2%)

# قاموس لتخزين البيانات التاريخية للعملات
coin_data = {}

async def send_telegram_alert(message):
    """إرسال تنبيه إلى تلجرام مع معالجة الأخطاء"""
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')
        logger.info("Telegram alert sent successfully.")
    except Exception as e:
        logger.error(f"Error sending telegram message: {e}")

async def process_kline(symbol, kline):
    """
    معالجة بيانات الشمعة والتحقق من شروط الانفجار (نسخة الفيوتشر)
    """
    try:
        if symbol not in coin_data:
            coin_data[symbol] = []

        # استخراج البيانات (سعر الإغلاق، حجم التداول)
        close_price = float(kline['c'])
        volume = float(kline['v'])
        
        coin_data[symbol].append({'price': close_price, 'volume': volume})

        # الاحتفاظ بآخر 21 شمعة فقط
        if len(coin_data[symbol]) > 21:
            coin_data[symbol].pop(0)

        if len(coin_data[symbol]) < 10:
            return

        # حساب المتوسطات
        df = pd.DataFrame(coin_data[symbol])
        avg_volume = df['volume'].iloc[:-1].mean()
        current_volume = df['volume'].iloc[-1]
        
        rvol = current_volume / avg_volume if avg_volume > 0 else 0
        price_change = ((close_price - df['price'].iloc[-2]) / df['price'].iloc[-2]) * 100

        # التحقق من الشروط (ارتفاع أو انخفاض حاد)
        # أضفنا خيار الانخفاض أيضاً لأن الفيوتشر يسمح بالبيع (Short)
        if rvol >= RVOL_THRESHOLD:
            direction = ""
            if price_change >= PRICE_CHANGE_THRESHOLD:
                direction = "🚀 *صعود (Long)*"
            elif price_change <= -PRICE_CHANGE_THRESHOLD:
                direction = "📉 *هبوط (Short)*"
            
            if direction:
                alert_msg = (
                    f"{direction} *تنبيه حركة فيوتشر!*\n\n"
                    f"💰 *العملة:* `{symbol}` (Futures)\n"
                    f"📈 *السعر:* `{close_price}`\n"
                    f"📊 *التغير:* `{price_change:+.2f}%` (1د)\n"
                    f"🔥 *حجم التداول النسبي (RVOL):* `{rvol:.2f}x`\n\n"
                    f"🔗 [تداول على Binance Futures](https://www.binance.com/en/futures/{symbol})"
                )
                logger.info(f"ALERT: {symbol} {direction} RVOL={rvol:.2f}, Change={price_change:.2f}%")
                await send_telegram_alert(alert_msg)
            
    except Exception as e:
        logger.error(f"Error processing kline for {symbol}: {e}")

async def main():
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.critical("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not found in environment variables.")
        return

    # استخدام عميل الفيوتشر
    client = await AsyncClient.create()
    bm = BinanceSocketManager(client)
    
    try:
        # الحصول على جميع أزواج USDT في سوق الفيوتشر
        exchange_info = await client.futures_exchange_info()
        symbols = [s['symbol'] for s in exchange_info['symbols'] if s['status'] == 'TRADING' and s['symbol'].endswith('USDT')]
        
        logger.info(f"Starting Futures scanner for {len(symbols)} symbols...")
        
        # باينانس تسمح بـ 1024 تيار لكل اتصال
        # سنراقب جميع عملات الفيوتشر (عادة تكون أقل من 300 عملة)
        streams = [f"{s.lower()}@kline_1m" for s in symbols]
        
        # ملاحظة: بالنسبة للفيوتشر نستخدم futures_multiplex_socket
        async with bm.futures_multiplex_socket(streams) as ms:
            while True:
                res = await ms.recv()
                if res and 'data' in res:
                    data = res['data']
                    symbol = data['s']
                    kline = data['k']
                    
                    # معالجة الشمعة عند إغلاقها
                    if kline['x']:
                        await process_kline(symbol, kline)
    except Exception as e:
        logger.error(f"Main loop error: {e}")
    finally:
        await client.close_connection()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
