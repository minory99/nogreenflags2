import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан. Скопируйте .env.example в .env и укажите токен от @BotFather.")

DB_PATH = os.getenv("DB_PATH", "flawmatch.db")

MIN_COMPAT_THRESHOLD = 0.34
GOOD_COMPAT_THRESHOLD = 0.65
