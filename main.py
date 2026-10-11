import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from database.connection import init_db
from handlers import common_router, admin_router, student_router
from middlewares import DbSessionMiddleware

# Loglarni sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


async def main():
    """Botni ishga tushiruvchi asosiy funksiya"""
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error(
            "XATOLIK: .env faylida BOT_TOKEN ko'rsatilmagan! "
            "Iltimos, @BotFather dan olingan tokenni .env fayliga kiriting."
        )
        return

    logger.info("Ma'lumotlar bazasi jadvallari tekshirilmoqda va yaratilmoqda...")
    try:
        await init_db()
        logger.info("Ma'lumotlar bazasi muvaffaqiyatli ishga tushirildi.")
    except Exception as e:
        logger.error(f"Ma'lumotlar bazasiga ulanishda xatolik yuz berdi: {e}", exc_info=True)
        return

    # Bot va Dispatcher obyektlari
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Middlewarelarni ro'yxatdan o'tkazish
    dp.update.middleware(DbSessionMiddleware())

    # Routerlarni qo'shish
    dp.include_router(common_router)
    dp.include_router(admin_router)
    dp.include_router(student_router)

    # Eski kutilmagan xabarlarni o'chirib, pollingni boshlash
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Maktab oylik test boti ishga tushdi! Polling boshlanmoqda...")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
