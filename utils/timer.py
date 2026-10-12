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

                    # O'quvchi va test ma'lumotlarini olish
                    from database.models import User, Test
                    from utils.notifier import send_result_to_group_and_admins

                    user = await session.get(User, user_id)
                    test = await session.get(Test, attempt.test_id)
                    test_title = test.title if test else "Test"

                    # Guruhga va adminlarga avtomatik yuborish
                    await send_result_to_group_and_admins(
                        bot=bot,
                        user_id=user_id,
                        full_name=user.full_name if user else "O'quvchi",
                        grade=user.grade if user else "-",
                        username=getattr(user, "username", None),
                        test_title=test_title,
                        score=score,
                        total_questions=total,
                        percentage=pct,
                        spent_time_str=f"{test.duration_minutes if test else 0} daqiqa (Vaqt tugadi)",
                    )

                    # O'quvchiga xabar yuborish
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"⏰ <b>Test uchun ajratilgan vaqt tugadi!</b>\n\n"
                                f"Sizning javoblaringiz qabul qilindi va test yakunlandi.\n"
                                f"📊 To'plangan ball: <b>{score} / {total}</b> ({pct:.1f}%)\n\n"
                                f"<i>Natijangiz guruhga va ustozga yuborildi.</i>"
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
