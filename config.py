import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# Admin IDs ro'yxati (env da bo'lmasa, standart fallback qiymatlar ishlaydi)
DEFAULT_ADMIN_IDS: list[int] = [1303759816, 5236823441]
raw_admin_ids: str = os.getenv("ADMIN_IDS", "")
env_admin_ids: list[int] = [
    int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().lstrip("-").isdigit()
]
# Barcha admin ID larini birlashtirish
ADMIN_IDS: list[int] = list(set(env_admin_ids + DEFAULT_ADMIN_IDS))

# Guruh chat ID (Natijalar yuboriladigan guruh, standart: -1004465820867)
raw_group_id: str = os.getenv("GROUP_CHAT_ID", "-1004465820867").strip()
try:
    GROUP_CHAT_ID: int = int(raw_group_id)
except ValueError:
    GROUP_CHAT_ID: int = -1004465820867

# Ma'lumotlar bazasi URL manzili
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///school_test.db").strip()

# Agar Supabase / PostgreSQL manzili oddiy "postgresql://" yoki "postgres://" bilan kelsa,
# SQLAlchemy asyncpg drayveri uchun uni "postgresql+asyncpg://" ga o'tkazish
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
