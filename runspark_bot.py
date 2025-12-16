import os
import logging
import requests
from datetime import datetime, time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from gtts import gTTS
from io import BytesIO
import pytz

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
VLADIVOSTOK_TZ = pytz.timezone("Asia/Vladivostok")

# === ПОГОДА ===
def get_weather():
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 43.1056,
            "longitude": 131.8735,
            "current": "temperature_2m,weather_code",
            "timezone": "Asia/Vladivostok"
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        current = data["current"]
        wmo = current["weather_code"]
        wmo_desc = {
            0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность", 3: "облачно",
            51: "слабый дождь", 53: "умеренный дождь", 55: "сильный дождь",
            61: "небольшой дождь", 63: "дождь", 65: "сильный дождь",
            71: "слабый снег", 73: "умеренный снег", 75: "сильный снег",
            95: "гроза"
        }.get(wmo, "погода неизвестна")
        return {"temp": current["temperature_2m"], "desc": wmo_desc}
    except Exception as e:
        logging.error(f"Weather error: {e}")
        return {"temp": 0, "desc": "погода недоступна"}

# === СЕЗОН ===
def get_season():
    m = datetime.now().month
    if m in [12, 1, 2]: return "зима"
    if m in [3, 4, 5]: return "весна"
    if m in [6, 7, 8]: return "лето"
    return "осень"

# === МОТИВАЦИЯ ===
def generate_message(mood: str, weather: dict, season: str, is_sunday: bool):
    distance = 15 if is_sunday else 10
    if any(kw in mood.lower() for kw in ["плох", "устал", "сплю", "не хочу"]):
        intro = "Ты проснулся не потому, что будильник зазвонил. Ты проснулся — потому что внутри тебя ещё жив огонь."
    elif any(kw in mood.lower() for kw in ["норм", "средне", "обычно"]):
        intro = "Привычка сильнее настроения. Ты уже прошёл этот путь сотни раз."
    else:
        intro = "Сегодня твой день! Мир ждёт твоих километров."

    if "дождь" in weather["desc"]:
        weather_line = f"Дождь — не помеха, а союзник. А {weather['temp']}° — идеально для бега."
    elif "снег" in weather["desc"] or weather["temp"] < -3:
        weather_line = f"Мороз и снег — твоя стихия. Зима закаляет дух."
    elif weather["temp"] > 25:
        weather_line = f"Жара? Это шанс проверить, насколько ты стоек."
    else:
        weather_line = f"Погода идеальна: {weather['desc']}, {weather['temp']}°."

    season_image = {
        "зима": "Твои следы на снегу — символ стойкости.",
        "весна": "Каждый шаг — часть возрождения.",
        "лето": "Используй энергию лета — выжми максимум!",
        "осень": "Осень — время сбора урожая усилий."
    }[season]

    return f"{intro}\n\nСегодня — {'воскресенье' if is_sunday else 'будний день'}. Цель: **{distance} км**.\n\n{weather_line}\n\n{season_image}\n\nОбувь завязана? Вперёд!"

# === ГОЛОС ===
async def send_voice(bot, chat_id, text):
    try:
        tts = gTTS(text=text, lang='ru', slow=False)
        audio = BytesIO()
        tts.write_to_fp(audio)
        audio.seek(0)
        await bot.send_voice(chat_id=chat_id, voice=audio)
    except:
        await bot.send_message(chat_id=chat_id, text="🔊 Голос временно недоступен.")

# === КОМАНДЫ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Каждое утро в 4:00 я пришлю мотивацию. Напиши /test — чтобы попробовать сейчас.")
    context.job_queue.run_daily(
        send_prompt,
        time=time(hour=4, minute=0, second=0),
        timezone=VLADIVOSTOK_TZ,
        chat_id=update.effective_chat.id
    )

async def send_prompt(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text="🌅 Доброе утро! Как настроение? (Ответь: отлично / нормально / плохо)"
    )

async def handle_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mood = update.message.text
    chat_id = update.effective_chat.id
    weather = get_weather()
    season = get_season()
    is_sunday = datetime.now(VLADIVOSTOK_TZ).weekday() == 6
    msg = generate_message(mood, weather, season, is_sunday)
    await update.message.reply_text(msg, parse_mode="Markdown")
    await send_voice(context.bot, chat_id, msg)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await handle_mood(update, context)

# === ЗАПУСК ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(Command("test", test))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mood))
    app.run_polling()