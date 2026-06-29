import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters, ConversationHandler
)

# ==================== تنظیمات ====================
BOT_TOKEN = "8905755036:AAERdugzBM-ohUmlwKB1xAp65oKLwxqD2D8"
CALLINOO_TOKEN = "8054751209:AEwcaJIqBCAz7u6BXCuzWErTaAPSaRKTAF0e6obWQ0WK"
API_BASE = "https://api.ozvinoo.xyz"
CALLINOO_HEADERS = {
    "Authorization": f"Bearer {CALLINOO_TOKEN}",
    "Content-Type": "application/json"
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== States ====================
SELECT_SERVICE, SELECT_COUNTRY, WAITING_CODE = range(3)

# ==================== API Helpers ====================

def get_balance():
    try:
        r = requests.get(f"{API_BASE}/web/{CALLINOO_TOKEN}/get-balance", timeout=10)
        data = r.json()
        return data.get("balance", 0)
    except:
        return None

def get_services():
    try:
        r = requests.post(f"{API_BASE}/web/{CALLINOO_TOKEN}/applications", timeout=10)
        return r.json() if r.ok else []
    except:
        return []

def get_prices(service_id):
    try:
        r = requests.post(f"{API_BASE}/web/{CALLINOO_TOKEN}/get-prices/{service_id}", timeout=10)
        return r.json() if r.ok else []
    except:
        return []

def get_number(service_id, country):
    try:
        r = requests.post(f"{API_BASE}/web/{CALLINOO_TOKEN}/getNumber/{service_id}/{country}", timeout=15)
        return r.json()
    except:
        return None

def get_code(request_id):
    try:
        r = requests.post(f"{API_BASE}/web/{CALLINOO_TOKEN}/getCode/{request_id}", timeout=10)
        return r.json()
    except:
        return None

def logout(request_id):
    try:
        r = requests.post(f"{API_BASE}/web/{CALLINOO_TOKEN}/logout/{request_id}", timeout=10)
        return r.json()
    except:
        return None

# ==================== Handlers ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    balance = get_balance()
    balance_text = f"{balance:,} تومان" if balance is not None else "نامشخص"

    text = (
        "🌟 *به NumPlus خوش آمدید!*\n\n"
        "🔢 فروش شماره مجازی تلگرام\n"
        f"💰 موجودی حساب: `{balance_text}`\n\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:"
    )
    keyboard = [
        [InlineKeyboardButton("📱 خرید شماره مجازی", callback_data="buy_number")],
        [InlineKeyboardButton("💰 موجودی حساب", callback_data="check_balance")],
        [InlineKeyboardButton("📞 پشتیبانی", callback_data="support")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "check_balance":
        balance = get_balance()
        if balance is not None:
            text = f"💰 موجودی حساب شما: *{balance:,} تومان*"
        else:
            text = "❌ خطا در دریافت موجودی. لطفاً دوباره امتحان کنید."
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "buy_number":
        await query.edit_message_text("⏳ در حال دریافت لیست سرویس‌ها...")
        services = get_services()
        if not services:
            await query.edit_message_text("❌ خطا در دریافت سرویس‌ها. لطفاً دوباره امتحان کنید.")
            return

        keyboard = []
        for s in services[:10]:  # max 10
            sid = s.get("id")
            title = s.get("title", "نامشخص")
            keyboard.append([InlineKeyboardButton(title, callback_data=f"service_{sid}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")])

        await query.edit_message_text(
            "📱 *انتخاب سرویس:*\nسرویس موردنظر را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("service_"):
        service_id = data.split("_")[1]
        context.user_data["service_id"] = service_id
        await query.edit_message_text("⏳ در حال دریافت قیمت‌ها و کشورها...")

        prices = get_prices(service_id)
        if not prices:
            await query.edit_message_text("❌ خطا در دریافت قیمت‌ها.")
            return

        # فقط کشورهایی که موجود هستند
        available = [p for p in prices if "موجود" in str(p.get("count", "")) and "ناموجود" not in str(p.get("count", ""))]
        if not available:
            available = prices[:15]

        keyboard = []
        for p in available[:12]:
            country = p.get("country", "نامشخص")
            price = p.get("price", 0)
            rng = p.get("range", "")
            keyboard.append([InlineKeyboardButton(
                f"{country} — {price:,} تومان",
                callback_data=f"country_{rng}"
            )])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="buy_number")])

        await query.edit_message_text(
            "🌍 *انتخاب کشور:*\nکشور موردنظر را انتخاب کنید:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("country_"):
        country = data.split("_", 1)[1]
        service_id = context.user_data.get("service_id")
        context.user_data["country"] = country

        await query.edit_message_text("⏳ در حال دریافت شماره مجازی...")
        result = get_number(service_id, country)

        if not result or "number" not in result:
            msg = result.get("error_msg", "خطای ناشناخته") if result else "خطا در اتصال"
            await query.edit_message_text(f"❌ خطا: {msg}")
            return

        number = result.get("number")
        request_id = result.get("request_id")
        price = result.get("price", 0)
        country_name = result.get("countery", country)
        quality = result.get("quality", "")

        context.user_data["request_id"] = request_id

        text = (
            f"✅ *شماره مجازی دریافت شد!*\n\n"
            f"📞 شماره: `{number}`\n"
            f"🌍 کشور: {country_name}\n"
            f"💰 قیمت: {price:,} تومان\n"
            f"🔖 کد درخواست: `{request_id}`\n\n"
            f"{quality}\n\n"
            f"⏳ منتظر کد تأیید باشید و روی دکمه زیر کلیک کنید:"
        )
        keyboard = [
            [InlineKeyboardButton("📨 دریافت کد تأیید", callback_data=f"getcode_{request_id}")],
            [InlineKeyboardButton("❌ لغو / خروج", callback_data=f"logout_{request_id}")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("getcode_"):
        request_id = int(data.split("_")[1])
        result = get_code(request_id)

        if result and result.get("code"):
            code = result["code"]
            number = result.get("number", "")
            text = (
                f"✅ *کد تأیید دریافت شد!*\n\n"
                f"📞 شماره: `{number}`\n"
                f"🔑 کد: `{code}`\n\n"
                f"این کد را در تلگرام وارد کنید."
            )
            keyboard = [
                [InlineKeyboardButton("🚪 خروج از حساب", callback_data=f"logout_{request_id}")],
                [InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")],
            ]
        else:
            text = "⏳ هنوز کدی ارسال نشده. چند لحظه صبر کنید و دوباره امتحان کنید."
            keyboard = [
                [InlineKeyboardButton("🔄 تلاش مجدد", callback_data=f"getcode_{request_id}")],
                [InlineKeyboardButton("❌ لغو", callback_data=f"logout_{request_id}")],
            ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("logout_"):
        request_id = int(data.split("_")[1])
        logout(request_id)
        keyboard = [[InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_main")]]
        await query.edit_message_text(
            "✅ با موفقیت از حساب خارج شدید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "support":
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]]
        await query.edit_message_text(
            "📞 *پشتیبانی NumPlus*\n\nبرای ارتباط با پشتیبانی پیام بفرستید:\n@NumPlusSupport",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "back_main":
        balance = get_balance()
        balance_text = f"{balance:,} تومان" if balance is not None else "نامشخص"
        text = (
            "🌟 *NumPlus*\n\n"
            "🔢 فروش شماره مجازی تلگرام\n"
            f"💰 موجودی حساب: `{balance_text}`\n\n"
            "یکی از گزینه‌های زیر را انتخاب کنید:"
        )
        keyboard = [
            [InlineKeyboardButton("📱 خرید شماره مجازی", callback_data="buy_number")],
            [InlineKeyboardButton("💰 موجودی حساب", callback_data="check_balance")],
            [InlineKeyboardButton("📞 پشتیبانی", callback_data="support")],
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ==================== Main ====================

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("NumPlus Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
