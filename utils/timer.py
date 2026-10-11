import asyncio
import logging
from datetime import datetime
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from database.connection import async_session_maker
from database.crud import get_attempt, finish_test_attempt

logger = logging.getLogger(__name__)

# Faol taymerlarni saqlash: attempt_id -> asyncio.Task
active_timers: dict[int, asyncio.Task] = {}


async def schedule_test_timer(
    bot: Bot,
    user_id: int,
    attempt_id: int,
    duration_seconds: int,
    state: FSMContext,
):
    """
    Belgilangan vaqt o'tgach, testni avtomatik yopuvchi asinxron taymer.
    O'quvchi javob berishni to'xtatsa ham, vaqt tugashi bilan test avtomatik yopiladi va natija yuboriladi.
    """
    async def _timer_worker():
        try:
            await asyncio.sleep(duration_seconds)

            # Bazadan attempt holatini tekshirish
            async with async_session_maker() as session:
                attempt = await session.get(get_attempt.__annotations__.get('return', object), attempt_id) if False else None
                # To'g'ridan-to'g'ri so'rov
                from database.models import TestAttempt
                attempt = await session.get(TestAttempt, attempt_id)

                if attempt and not attempt.is_completed:
                    score = attempt.score
                    total = attempt.total_questions
                    pct = (score / total * 100) if total > 0 else 0.0

                    await finish_test_attempt(session, attempt_id, score, pct)

                    # FSM holatini tozalash
                    await state.clear()

                    # O'quvchiga xabar yuborish
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"⏰ <b>Test uchun ajratilgan vaqt tugadi!</b>\n\n"
                                f"Sizning javoblaringiz qabul qilindi va test yakunlandi.\n"
                                f"📊 To'plangan ball: <b>{score} / {total}</b> ({pct:.1f}%)\n\n"
                                f"Natijalaringizni ko'rish uchun <b>📊 Natijalarim</b> bo'limiga o'ting."
                            ),
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"O'quvchiga vaqt tugashi haqida xabar yuborilmadi: {e}")

        except asyncio.CancelledError:
            # Agar o'quvchi testni o'zi vaqtidan oldin tugatsa, taymer bekor qilinadi
            pass
        except Exception as e:
            logger.error(f"Taymer xatoligi: {e}", exc_info=True)
        finally:
            active_timers.pop(attempt_id, None)

    # Oldingi taymer bo'lsa bekor qilish
    cancel_test_timer(attempt_id)

    task = asyncio.create_task(_timer_worker())
    active_timers[attempt_id] = task


def cancel_test_timer(attempt_id: int):
    """Taymerni bekor qilish (o'quvchi barcha savollarni ishlab bo'lganda)"""
    task = active_timers.pop(attempt_id, None)
    if task and not task.done():
        task.cancel()
