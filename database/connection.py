from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import config
from database.models import Base

# SQLAlchemy asinxron engine
engine = create_async_engine(
    config.DATABASE_URL,
    echo=False,
    future=True,
)

# Sessiyalar fabrikasi
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Barcha jadvallarni ma'lumotlar bazasida yaratish (agar mavjud bo'lmasa)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Yangi ma'lumotlar bazasi sessiyasini olish"""
    async with async_session_maker() as session:
        yield session
