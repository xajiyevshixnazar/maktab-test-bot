import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# Admin IDs ro'yxati
raw_admin_ids: str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()
]

# Ma'lumotlar bazasi URL manzili
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///school_test.db").strip()

# Agar Supabase / PostgreSQL manzili oddiy "postgresql://" yoki "postgres://" bilan kelsa,
# SQLAlchemy asyncpg drayveri uchun uni "postgresql+asyncpg://" ga o'tkazish
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
