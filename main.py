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

import os
import aiohttp
from aiohttp import web

# Loglarni sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


async def start_health_server(port: int):
    """Render.com Web Service sifatida sog'liq tekshiruvi (Health Check) uchun web server"""
    async def handle_ping(request):
        return web.Response(text="OK - Maktab Test Bot is running!", status=200)

    app = web.Application()
    app.router.add_get("/", handle_ping)
    app.router.add_get("/health", handle_ping)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Render sog'liq tekshiruvi serveri 0.0.0.0:{port} da ishga tushirildi.")


async def keep_alive_task():
    """Render bepul tarifida bot uxlab qolmasligi uchun har 10 daqiqada o'zini uyg'otib turish"""
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if not render_url:
        return
    await asyncio.sleep(60)
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{render_url}/health", timeout=15) as resp:
                    logger.info(f"Keep-alive ping muvaffaqiyatli: {resp.status}")
        except Exception as e:
            logger.debug(f"Keep-alive ping xatosi: {e}")
        await asyncio.sleep(600)


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

    # Global xatoliklar nazorati: kutilmagan xatolik yuz berganda adminga xabar berish
    from aiogram.types import ErrorEvent
    @dp.error()
    async def global_error_handler(event: ErrorEvent):
        logger.error(f"Kutilmagan xatolik: {event.exception}", exc_info=True)
        try:
            from utils.notifier import notify_error_to_admins
            await notify_error_to_admins(
                bot=event.bot,
                error_msg=str(event.exception)[:350],
                context=f"Update turi: {event.update.event_type if event.update else 'unknown'}"
            )
        except Exception as err:
            logger.error(f"Adminga xatolik yetkazishda muammo: {err}")

    # Eski kutilmagan xabarlarni o'chirib, pollingni boshlash
    await bot.delete_webhook(drop_pending_updates=True)

    # Render.com yoki bulutli hostinglar uchun (agar PORT muhit o'zgaruvchisi berilgan bo'lsa)
    port = os.getenv("PORT")
    if port:
        try:
            await start_health_server(int(port))
            asyncio.create_task(keep_alive_task())
        except Exception as e:
            logger.warning(f"Sog'liq serverini ishga tushirishda ogohlantirish: {e}")

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
