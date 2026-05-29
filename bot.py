import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
import anthropic

# ── Logging ──
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Keys ──
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY")

# ── Conversation states ──
CHOOSE_TYPE, GET_DETAILS, GET_NAME, GET_ADDRESS, CONFIRM = range(5)

# ── Complaint types ──
COMPLAINT_TYPES = [
    ["🏠 Комунальні послуги", "🏦 Банк / Фінанси"],
    ["📡 Інтернет / Зв'язок", "🏥 Медицина"],
    ["🛒 Магазин / Товар", "📦 Доставка / Пошта"],
    ["🏛️ Держорган", "⚡ Енергопостачання"],
]

# ── System prompt ──
SYSTEM_PROMPT = """Ти — юридичний асистент для громадян України. 
Твоє завдання — складати офіційні скарги, претензії та заяви.

Правила:
1. Якщо користувач пише українською — відповідай українською
2. Якщо користувач пише російською — відповідай російською
3. Використовуй офіційно-діловий стиль
4. Посилайся на конкретні статті законів України
5. Структура: шапка → суть проблеми → вимоги → підпис
6. Документ має бути готовий до відправки без змін
7. Додавай реалістичні строки відповіді (7-30 днів залежно від типу)
8. Завжди вказуй що це претензія/скарга в офіційному сенсі

Ти НЕ даєш юридичних консультацій — ти допомагаєш скласти документ.
Після документу додай коротку підказку: куди і як його краще подати."""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    welcome = (
        "👋 *Вітаю в AI-Скаржнику!*\n\n"
        "Я допомагаю скласти офіційну скаргу або претензію за лічені хвилини.\n\n"
        "Просто опишіть проблему — я згенерую готовий документ з посиланнями на закони.\n\n"
        "⚠️ _Сервіс надає шаблони документів. Це не юридична консультація._\n\n"
        "Натисніть /complaint щоб почати 👇"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def new_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = ReplyKeyboardMarkup(
        COMPLAINT_TYPES,
        one_time_keyboard=True,
        resize_keyboard=True
    )
    await update.message.reply_text(
        "📋 *Оберіть тип скарги:*",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    return CHOOSE_TYPE


async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["type"] = update.message.text
    await update.message.reply_text(
        f"✅ Тип: *{update.message.text}*\n\n"
        "📝 Тепер опишіть проблему детально:\n\n"
        "_Наприклад: Вже 3 місяці не ремонтують дах, вода затікає у квартиру, "
        "звертався до ОСББ двічі але ігнорують._",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown"
    )
    return GET_DETAILS


async def get_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["details"] = update.message.text
    await update.message.reply_text(
        "👤 Ваше *повне ім'я* (ПІБ):\n\n"
        "_Наприклад: Петренко Іван Васильович_",
        parse_mode="Markdown"
    )
    return GET_NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        "🏠 Ваша *адреса* (місто, вулиця, квартира):\n\n"
        "_Наприклад: м. Київ, вул. Хрещатик 1, кв. 5_",
        parse_mode="Markdown"
    )
    return GET_ADDRESS


async def get_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text
    await update.message.reply_text(
        "⏳ *Генерую документ...*\n\n"
        "_Зазвичай займає 10-15 секунд_",
        parse_mode="Markdown"
    )

    user_prompt = f"""Склади офіційну скаргу/претензію. Визнач мову за деталями проблеми і використовуй ту саму мову для документу.

Тип: {context.user_data.get('type', '')}
Проблема: {context.user_data.get('details', '')}
ПІБ заявника: {context.user_data.get('name', '')}
Адреса: {context.user_data.get('address', '')}
Дата: {__import__('datetime').date.today().strftime('%d.%m.%Y')}

Згенеруй повний готовий документ."""

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )
        document = message.content[0].text

        await update.message.reply_text(
            f"✅ *Ваш документ готовий:*\n\n{document}",
            parse_mode="Markdown"
        )

        keyboard = ReplyKeyboardMarkup(
            [["📄 Нова скарга", "❓ Допомога"]],
            one_time_keyboard=True,
            resize_keyboard=True
        )
        await update.message.reply_text(
            "📌 *Що далі?*\n\n"
            "Скопіюйте документ → роздрукуйте або надішліть електронно.\n\n"
            "Потрібна ще одна скарга?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"API error: {e}")
        await update.message.reply_text(
            "❌ Виникла помилка. Спробуйте ще раз — /complaint"
        )

    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Як користуватися AI-Скаржником:*\n\n"
        "1️⃣ /complaint — почати нову скаргу\n"
        "2️⃣ Обрати тип проблеми\n"
        "3️⃣ Описати ситуацію\n"
        "4️⃣ Вказати ім'я та адресу\n"
        "5️⃣ Отримати готовий документ\n\n"
        "⚠️ _Документи є шаблонами. Для складних справ зверніться до юриста._",
        parse_mode="Markdown"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Скасовано. Натисніть /complaint щоб почати знову.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "Нова скарга" in text:
        return await new_complaint(update, context)
    elif "Допомога" in text:
        return await help_command(update, context)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("complaint", new_complaint),
            CommandHandler("start", new_complaint),
        ],
        states={
            CHOOSE_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_type)],
            GET_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_details)],
            GET_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GET_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_address)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))


if __name__ == "__main__":
    main()
