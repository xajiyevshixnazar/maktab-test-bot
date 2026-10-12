import logging
from datetime import datetime
from aiogram import Bot
import config

logger = logging.getLogger(__name__)


async def send_result_to_group_and_admins(
    bot: Bot,
    user_id: int,
    full_name: str,
    grade: str,
    username: str | None,
    test_title: str,
    score: int,
    total_questions: int,
    percentage: float,
    spent_time_str: str,
):
    """
    O'quvchi test/topshiriqni topshirganda natijani -1004465820867 ID li guruhga
    va kerak bo'lsa adminlarga chiroyli HTML formatida yuborish.
    """
    username_text = f"@{username}" if username else "Mavjud emas"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    msg_text = (
        "📊 <b>YANGI TEST NATIJASI TOPSHIRILDI</b>\n\n"
        f"👤 <b>O'quvchining F.I.Sh:</b> {full_name}\n"
        f"🏫 <b>Sinf / Guruh:</b> {grade}\n"
        f"🔗 <b>Telegram username:</b> {username_text}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n\n"
        f"📝 <b>Test nomi:</b> {test_title}\n"
        f"🎯 <b>Natija:</b> <b>{score} / {total_questions}</b> ({percentage:.1f}%)\n"
        f"✅ <b>To'g'ri javoblar:</b> {score} ta\n"
        f"❌ <b>Noto'g'ri javoblar:</b> {total_questions - score} ta\n"
        f"⏱ <b>Sarflangan vaqt:</b> {spent_time_str}\n\n"
        f"📅 <b>Yuborilgan sana va vaqt:</b> {now_str}"
    )

    # 1. Belgilangan guruhga yuborish
    try:
        await bot.send_message(
            chat_id=config.GROUP_CHAT_ID,
            text=msg_text,
            parse_mode="HTML"
        )
        logger.info(f"Test natijasi guruhga ({config.GROUP_CHAT_ID}) yuborildi.")
    except Exception as e:
        logger.error(f"Guruhga ({config.GROUP_CHAT_ID}) natija yuborishda xatolik: {e}")
        # Agar bot guruhda bo'lmasa yoki huquqi bo'lmasa, adminga ogohlantirish yuborish
        for admin_id in config.ADMIN_IDS:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"⚠️ <b>OGOHLANTIRISH:</b> Guruhga xabar yuborilmadi!\n"
                        f"Guruh ID: <code>{config.GROUP_CHAT_ID}</code>\n"
                        f"Xatolik: <i>{e}</i>\n\n"
                        f"💡 <i>Iltimos, botni guruhga qo'shib, xabar yozish huquqini (adminlik) bering.</i>\n\n"
                        f"<b>O'quvchi natijasi:</b>\n{msg_text}"
                    ),
                    parse_mode="HTML"
                )
            except Exception as admin_err:
                logger.error(f"Adminga ({admin_id}) xatolik xabarini yuborishda muammo: {admin_err}")


async def notify_admins(bot: Bot, text: str):
    """Barcha adminlarga xabar yuborish"""
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Adminga ({admin_id}) xabar yuborilmadi: {e}")


async def notify_error_to_admins(bot: Bot, error_msg: str, context: str = ""):
    """Tizimda xatolik yuz berganda adminlarni ogohlantirish"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = (
        f"🚨 <b>TIZIM XATOLIGI ANIQLANDI!</b>\n\n"
        f"📍 <b>Joylashuv:</b> {context}\n"
        f"⏰ <b>Sana va vaqt:</b> {now_str}\n"
        f"⚠️ <b>Xatolik matni:</b> <code>{error_msg}</code>"
    )
    await notify_admins(bot, text)
