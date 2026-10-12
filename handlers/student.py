import time
import random
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.crud import (
    get_user,
    get_active_tests,
    get_test,
    get_attempt,
    start_test_attempt,
    record_answer,
    finish_test_attempt,
    get_user_attempts,
    get_questions_for_test,
)
from keyboards.inline import (
    get_active_tests_keyboard,
    get_start_test_confirm_keyboard,
    get_question_options_keyboard,
)
from states.test_taking import TestTakingState
from utils.timer import schedule_test_timer, cancel_test_timer
from utils.notifier import send_result_to_group_and_admins

router = Router(name="student_router")


# ==================== TESTLAR RO'YXATINI KO'RISH ====================

@router.message(F.text == "📝 Testlar")
async def show_active_tests(message: Message, session: AsyncSession, state: FSMContext):
    """Faol testlar ro'yxatini ko'rsatish"""
    user_id = message.from_user.id
    user = await get_user(session, user_id)
    if not user:
        from states.registration import RegistrationState
        await state.set_state(RegistrationState.waiting_for_full_name)
        await message.answer(
            "Assalomu alaykum! Maktab oylik test tizimiga xush kelibsiz.\n\n"
            "Testlarni ko'rish va topshirish uchun avval 1 marta ro'yxatdan o'tishingiz kerak.\n\n"
            "Iltimos, <b>Ism va Familiyangizni</b> kiriting:\n"
            "<i>(Masalan: Saidov Jasur)</i>",
            parse_mode="HTML"
        )
        return

    tests = await get_active_tests(session)
    if not tests:
        await message.answer(
            "📭 Hozirda hech qanday faol test mavjud emas.\n"
            "Ustozingiz testni faollashtirganida bu yerda paydo bo'ladi."
        )
        return

    text = (
        "📚 <b>Hozirda ochiq bo'lgan testlar:</b>\n\n"
        "Kerakli testni tanlang va topshirishni boshlang:"
    )
    await message.answer(text, reply_markup=get_active_tests_keyboard(tests), parse_mode="HTML")


@router.callback_query(F.data.startswith("student_select_test:"))
async def select_test_callback(callback: CallbackQuery, session: AsyncSession):
    """O'quvchi testni tanlaganda uning ma'lumotlarini ko'rsatish"""
    test_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    # 1 martalik topshirish tekshiruvi:
    attempt = await get_attempt(session, test_id=test_id, user_id=user_id)
    if attempt and attempt.is_completed:
        await callback.answer(
            "⚠️ Siz bu testni topshirgansiz! Qayta topshirish taqiqlangan.",
            show_alert=True
        )
        return

    test = await get_test(session, test_id)
    if not test or not test.is_active:
        await callback.answer("⛔️ Ushbu test ustoz tomonidan yopilgan (OFF holatda)!", show_alert=True)
        return

    q_count = len(test.questions)
    if q_count == 0:
        await callback.answer("⚠️ Bu testga hali savollar yuklanmagan.", show_alert=True)
        return

    text = (
        f"📖 <b>Test nomi:</b> {test.title}\n"
        f"❓ <b>Savollar soni:</b> {q_count} ta\n"
        f"⏱ <b>Ajratilgan vaqt:</b> {test.duration_minutes} daqiqa\n\n"
        "⚠️ <b>DIQQAT:</b>\n"
        "• Testni faqat <b>1 marta</b> topshirish mumkin.\n"
        "• Boshlash tugmasini bosishingiz bilan vaqt orqaga hisoblana boshlaydi.\n"
        "• Belgilangan vaqt tugasa, test avtomatik yopiladi!\n\n"
        "Testni boshlashga tayyormisiz?"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_start_test_confirm_keyboard(test_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_test_select")
async def cancel_test_selection(callback: CallbackQuery, session: AsyncSession):
    """Test tanlashni bekor qilib, ro'yxatga qaytish"""
    tests = await get_active_tests(session)
    if not tests:
        await callback.message.edit_text("Hozirda hech qanday faol test mavjud emas.")
        return

    await callback.message.edit_text(
        "📚 <b>Hozirda ochiq bo'lgan testlar:</b>",
        reply_markup=get_active_tests_keyboard(tests),
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== TESTNI BOSHLASH VA JAVOBLAR ====================

@router.callback_query(F.data.startswith("start_test:"))
async def start_test_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot
):
    """O'quvchi 'Testni boshlash' tugmasini bosganda"""
    test_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    # 1 martalik cheklovni qayta qat'iy tekshirish
    attempt = await get_attempt(session, test_id=test_id, user_id=user_id)
    if attempt and attempt.is_completed:
        await callback.answer("⚠️ Siz ushbu testni allaqachon topshirgansiz!", show_alert=True)
        return

    test = await get_test(session, test_id)
    if not test or not test.is_active:
        await callback.answer("⛔️ Ushbu test ustoz tomonidan yopilgan (OFF holatda)!", show_alert=True)
        return

    questions = await get_questions_for_test(session, test_id)
    if not questions:
        await callback.answer("⚠️ Testda savollar mavjud emas!", show_alert=True)
        return

    # Urinishni bazada ro'yxatdan o'tkazish
    if not attempt:
        attempt = await start_test_attempt(
            session=session,
            test_id=test_id,
            user_id=user_id,
            total_questions=len(questions)
        )
    else:
        # Agar avvalgi urinish tugallanmagan bo'lsa (masalan bot qayta ishga tushganda), tozalab qayta boshlash
        from sqlalchemy import delete
        from database.models import StudentAnswer
        await session.execute(delete(StudentAnswer).where(StudentAnswer.attempt_id == attempt.id))
        attempt.score = 0
        attempt.percentage = 0.0
        attempt.started_at = datetime.utcnow()
        await session.commit()

    # Savollar va variantlarni har bir o'quvchi uchun alohida tasodifiy aralashtirish (Random)
    prepared_questions = []
    letters = ["A", "B", "C", "D"]

    for q in questions:
        norm_correct = (q.correct_option or "A").strip().upper()
        # Original variantlar va to'g'ri javob belgisi
        opts_with_flag = [
            (q.option_a, norm_correct == "A"),
            (q.option_b, norm_correct == "B"),
            (q.option_c, norm_correct == "C"),
            (q.option_d, norm_correct == "D"),
        ]
        # Variantlar o'rnini aralashtirish (A, B, C, D har bir o'quvchida har xil bo'ladi)
        random.shuffle(opts_with_flag)

        shuffled_opts = {}
        shuffled_correct = "A"
        for idx, (opt_text, is_correct) in enumerate(opts_with_flag):
            letter = letters[idx]
            shuffled_opts[letter] = opt_text
            if is_correct:
                shuffled_correct = letter

        prepared_questions.append({
            "question_id": q.id,
            "question_text": q.question_text,
            "options": shuffled_opts,
            "correct_letter": shuffled_correct,
        })

    # Savollarning ketma-ketligini ham har bir o'quvchi uchun alohida aralashtirish
    random.shuffle(prepared_questions)

    duration_seconds = test.duration_minutes * 60
    start_ts = time.time()

    await state.set_state(TestTakingState.taking_test)
    await state.update_data(
        attempt_id=attempt.id,
        test_id=test_id,
        test_title=test.title,
        questions=prepared_questions,
        current_index=0,
        score=0,
        duration_seconds=duration_seconds,
        start_ts=start_ts,
    )

    # Asinxron vaqt nazorati taymerini ishga tushirish
    await schedule_test_timer(
        bot=bot,
        user_id=user_id,
        attempt_id=attempt.id,
        duration_seconds=duration_seconds,
        state=state
    )

    await callback.answer("🚀 Test boshlandi! Omad tilaymiz!")
    await render_question(callback.message, prepared_questions[0], 0, len(prepared_questions), duration_seconds)


async def render_question(
    message: Message,
    question_data: dict,
    index: int,
    total: int,
    remaining_secs: int
):
    """Savol matni va variantlarini chiqaruvchi yordamchi funksiya"""
    opts = question_data["options"]
    rem_min = max(0, remaining_secs // 60)

    text = (
        f"❓ <b>{index + 1} / {total}-savol</b>  (⏱ ~{rem_min} daqiqa qoldi)\n\n"
        f"<b>{question_data['question_text']}</b>\n\n"
        f"A) {opts['A']}\n"
        f"B) {opts['B']}\n"
        f"C) {opts['C']}\n"
        f"D) {opts['D']}\n\n"
        "<i>Quyidagi tugmalardan to'g'ri deb bilgan javobingizni tanlang:</i>"
    )
    keyboard = get_question_options_keyboard(index, ["A", "B", "C", "D"])
    await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")


@router.callback_query(TestTakingState.taking_test, F.data.startswith("ans:"))
async def process_answer_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession
):
    """O'quvchi javob variantini bosganda"""
    _, q_idx_str, chosen_letter = callback.data.split(":")
    q_index = int(q_idx_str)

    data = await state.get_data()
    attempt_id = data.get("attempt_id")
    questions = data.get("questions", [])
    current_index = data.get("current_index", 0)
    score = data.get("score", 0)
    start_ts = data.get("start_ts", time.time())
    duration_seconds = data.get("duration_seconds", 1800)
    test_title = data.get("test_title", "Test")

    # Qayta bir xil savolni bosib yuborishdan himoya
    if q_index != current_index:
        await callback.answer()
        return

    # Vaqt nazorati: vaqt tugaganmi?
    elapsed = time.time() - start_ts
    if elapsed > duration_seconds:
        cancel_test_timer(attempt_id)
        total = len(questions)
        pct = (score / total * 100) if total > 0 else 0.0
        await finish_test_attempt(session, attempt_id, score, pct)
        await state.clear()

        user = await get_user(session, callback.from_user.id)
        full_name_str = user.full_name if user else (callback.from_user.full_name or "O'quvchi")
        grade_str = user.grade if user else "-"

        # Natijani avtomatik ravishda belgilangan guruhga yuborish
        await send_result_to_group_and_admins(
            bot=callback.bot,
            user_id=callback.from_user.id,
            full_name=full_name_str,
            grade=grade_str,
            username=callback.from_user.username,
            test_title=test_title,
            score=score,
            total_questions=total,
            percentage=pct,
            spent_time_str=f"{int(duration_seconds // 60)} daqiqa (Vaqt tugadi)",
        )

        await callback.message.edit_text(
            f"⏰ <b>Vaqt tugadi!</b>\n\n"
            f"Ajratilgan vaqt tugaganligi sababli test yakunlandi.\n"
            f"📊 Natijangiz: <b>{score} / {total}</b> ({pct:.1f}%)\n\n"
            f"<i>Natijangiz guruhga va ustozga yuborildi.</i>",
            parse_mode="HTML"
        )
        await callback.answer("Vaqt tugadi!", show_alert=True)
        return

    # Javobni tekshirish
    curr_q = questions[current_index]
    is_correct = (chosen_letter.upper() == curr_q["correct_letter"].upper())
    if is_correct:
        score += 1

    # Javobni bazaga saqlash
    await record_answer(
        session=session,
        attempt_id=attempt_id,
        question_id=curr_q["question_id"],
        selected_option=chosen_letter.upper(),
        is_correct=is_correct,
    )

    next_index = current_index + 1
    total_q = len(questions)

    if next_index < total_q:
        # Keyingi savolga o'tish
        rem_secs = max(0, int(duration_seconds - elapsed))
        await state.update_data(current_index=next_index, score=score)
        await render_question(
            message=callback.message,
            question_data=questions[next_index],
            index=next_index,
            total=total_q,
            remaining_secs=rem_secs
        )
        await callback.answer()
    else:
        # Barcha savollar tugadi!
        cancel_test_timer(attempt_id)
        spent_seconds = int(time.time() - start_ts)
        spent_min = spent_seconds // 60
        spent_sec = spent_seconds % 60
        spent_time_str = f"{spent_min} daqiqa {spent_sec} soniya"

        percentage = (score / total_q * 100) if total_q > 0 else 0.0
        await finish_test_attempt(session, attempt_id, score, percentage)
        await state.clear()

        user = await get_user(session, callback.from_user.id)
        user_info = f"{user.full_name} ({user.grade})" if user else ""
        full_name_str = user.full_name if user else (callback.from_user.full_name or "O'quvchi")
        grade_str = user.grade if user else "-"

        # Natijani avtomatik ravishda belgilangan guruhga va adminlarga yuborish
        await send_result_to_group_and_admins(
            bot=callback.bot,
            user_id=callback.from_user.id,
            full_name=full_name_str,
            grade=grade_str,
            username=callback.from_user.username,
            test_title=test_title,
            score=score,
            total_questions=total_q,
            percentage=percentage,
            spent_time_str=spent_time_str,
        )

        result_text = (
            "🎉 <b>TEST YAKUNLANDI!</b>\n\n"
            f"📚 Test: <b>{test_title}</b>\n"
            f"👤 O'quvchi: <b>{user_info}</b>\n"
            f"⏱ Sarflangan vaqt: <b>{spent_time_str}</b>\n\n"
            f"✅ To'g'ri javoblar: <b>{score} ta</b>\n"
            f"❌ Noto'g'ri javoblar: <b>{total_q - score} ta</b>\n"
            f"📊 Jami savollar: <b>{total_q} ta</b>\n"
            f"🎯 <b>Natija: {percentage:.1f}%</b>\n\n"
            "<i>Natijangiz saqlandi hamda guruhga va ustozga yuborildi.</i>"
        )
        await callback.message.edit_text(result_text, parse_mode="HTML")
        await callback.answer("Test yakunlandi!")


@router.callback_query(F.data.startswith("ans:"))
async def stale_answer_fallback(callback: CallbackQuery, state: FSMContext):
    """Eski yoki uzilib qolgan test javoblari bosilganda qotib qolmaslik uchun"""
    await callback.answer(
        "⚠️ Test sessiyasi to'xtatilgan yoki yangilangan.\nIltimos, «📝 Testlar» tugmasi orqali qaytadan boshlang!",
        show_alert=True
    )
    try:
        await callback.message.edit_text(
            "⚠️ <b>Test sessiyasi uzildi!</b>\n\n"
            "Bot qayta ishga tushirilganligi yoki vaqt o'tganligi sababli test to'xtatildi.\n"
            "Iltimos, menyudagi <b>«📝 Testlar»</b> tugmasi orqali testni qaytadan topshiring.",
            parse_mode="HTML"
        )
    except Exception:
        pass


# ==================== O'QUVCHI NATIJALARI ====================

@router.message(F.text == "📊 Natijalarim")
async def show_my_results(message: Message, session: AsyncSession, state: FSMContext):
    """O'quvchining o'z natijalari tarixi"""
    user_id = message.from_user.id
    user = await get_user(session, user_id)
    if not user:
        from states.registration import RegistrationState
        await state.set_state(RegistrationState.waiting_for_full_name)
        await message.answer(
            "Natijalaringizni ko'rish uchun avval ro'yxatdan o'tishingiz kerak.\n\n"
            "Iltimos, <b>Ism va Familiyangizni</b> kiriting:\n"
            "<i>(Masalan: Saidov Jasur)</i>",
            parse_mode="HTML"
        )
        return

    attempts = await get_user_attempts(session, user_id)

    if not attempts:
        await message.answer(
            "Siz hali biron marta ham test topshirmagansiz.\n"
            "<b>📝 Testlar</b> bo'limidan ochiq testlarni topshirishingiz mumkin.",
            parse_mode="HTML"
        )
        return

    text_lines = ["📊 <b>Sizning test natijalaringiz:</b>\n"]
    for idx, att in enumerate(attempts, start=1):
        test_title = att.test.title if att.test else "Test"
        status = "✅ Yakunlangan" if att.is_completed else "⏳ Tugallanmagan"
        date_str = att.started_at.strftime("%Y-%m-%d %H:%M") if att.started_at else "-"

        text_lines.append(
            f"{idx}. <b>{test_title}</b>\n"
            f"   • Ball: <b>{att.score} / {att.total_questions}</b> ({att.percentage:.1f}%)\n"
            f"   • Holat: {status}\n"
            f"   • Sana: {date_str}\n"
        )

    await message.answer("\n".join(text_lines), parse_mode="HTML")
