# Crypto Pump Detection Bot 🚀

بوت احترافي لمراقبة العملات الرقمية على منصة باينانس واكتشاف الانفجارات السعرية وحجم التداول غير الطبيعي بشكل لحظي وإرسال تنبيهات عبر تلجرام.

## المميزات
- مراقبة لحظية لأكثر من 200 زوج USDT.
- اكتشاف الارتفاع المفاجئ في حجم التداول (Relative Volume).
- اكتشاف الزخم السعري (Price Momentum).
- تنبيهات فورية عبر تلجرام مع روابط مباشرة للمنصة.

## المتطلبات
- Python 3.9+
- Telegram Bot Token
- Telegram Chat ID

## الإعداد (Local)
1. قم بتثبيت المكتبات:
   ```bash
   pip install -r requirements.txt
   ```
2. قم بإنشاء ملف `.env` وأضف بياناتك:
   ```env
   TELEGRAM_TOKEN=your_token_here
   TELEGRAM_CHAT_ID=your_chat_id_here
   ```
3. شغل البوت:
   ```bash
   python main.py
   ```

## النشر على Railway 🚂
1. ارفع الكود إلى مستودع جديد على **GitHub**.
2. اذهب إلى [Railway.app](https://railway.app/).
3. أنشئ مشروعاً جديداً واربطه بمستودع GitHub.
4. أضف المتغيرات البيئية (Variables) في إعدادات المشروع على Railway:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. سيقوم Railway بنشر البوت تلقائياً وسيعمل 24/7.

## كيف يعمل البوت؟
يستخدم البوت معادلة **Relative Volume (RVOL)**:
- يحسب متوسط حجم التداول لآخر 20 دقيقة.
- إذا زاد حجم التداول في الدقيقة الحالية عن 5 أضعاف المتوسط مع ارتفاع سعري > 2%، يتم إرسال التنبيه.
