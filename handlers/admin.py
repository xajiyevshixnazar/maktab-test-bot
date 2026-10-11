import io
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

import config
from database.crud import (
    get_user,
    create_test,
    add_questions_bulk,
    get_all_tests,
    get_test,
    set_test_active_status,
    delete_test,
    get_test_leaderboard,
)
from keyboards.default import get_admin_main_keyboard, get_cancel_keyboard
from keyboards.inline import (
    get_admin_tests_list_keyboard,
    get_admin_test_control_keyboard,
    get_confirm_delete_keyboard,
)
from states.admin_states import CreateTestState
from utils.excel_helper import (
    create_excel_template,
    parse_questions_from_excel,
    generate_results_excel,
    generate_results_csv,
)
from utils.question_parser import parse_questions_from_text

router = Router(name="admin_router")


def is_admin_check(user_id: int) -> bool:
    """Faqat .env dagi ADMIN_IDS dagi foydalanuvchilar kira oladi"""
    return user_id in config.ADMIN_IDS


# ==================== SHABLONLARNI YUKLASH ====================

@router.message(F.text.in_(["📄 Excel shablon olish", "📄 Shablon olish"]))
async def send_excel_template(message: Message):
    """O'qituvchiga savollar kiritish uchun tayyor Bloknot (.txt) va Excel (.xlsx) shablon fayllarini yuborish"""
    if not is_admin_check(message.from_user.id):
        return

    # 1. Bloknot (.txt) shabloni - Noutbukda Excel bo'lmaganda eng qulayi!
    sample_txt = (
        "1. O'zbekiston poytaxti qaysi shahar?\n"
        "A) Samarqand\n"
        "B) Toshkent\n"
        "C) Buxoro\n"
        "D) Xiva\n"
        "Javob: B\n"
        "===\n"
        "2. 5 * (12 - 4) ifodaning qiymatini toping.\n"
        "A) 40\n"
        "B) 35\n"
        "C) 45\n"
        "D) 50\n"
        "Javob: A\n"
        "===\n"
        "3. Alisher Navoiy qaysi asrning buyuk shoiri hisoblanadi?\n"
        "A) XIV asr\n"
        "B) XV asr\n"
        "C) XVI asr\n"
        "D) XIII asr\n"
        "Javob: B\n"
    )
    doc_txt = BufferedInputFile(sample_txt.encode("utf-8-sig"), filename="test_savollar_shablon.txt")
    await message.answer_document(
        document=doc_txt,
        caption=(
            "📝 <b>Bloknot (Notepad) uchun tayyor shablon!</b>\n\n"
            "Agar noutbukingizda Excel dasturi bo'lmasa, mana shu faylni Bloknotda ochib, "
            "o'z savollaringizni yozib botga yuborishingiz mumkin."
        ),
        parse_mode="HTML"
    )

    # 2. Excel (.xlsx) shabloni - Excel dasturi borlar yoki telefon uchun
    stream = create_excel_template()
    doc_xlsx = BufferedInputFile(stream.getvalue(), filename="test_savollar_shablon.xlsx")
    await message.answer_document(
        document=doc_xlsx,
        caption=(
            "📊 <b>Excel (.xlsx) shablon fayli</b>\n\n"
            "<i>(Diqqat: Ushbu faylni Microsoft Excel, WPS Office yoki Google Sheets ilovasida oching. Bloknotda ochilsa kod ko'rinadi).</i>"
        ),
        parse_mode="HTML"
    )


# ==================== YANGI TEST YARATISH (FSM) ====================

@router.message(F.text == "➕ Yangi test yaratish")
async def start_create_test(message: Message, state: FSMContext):
    """Test yaratish jarayonini boshlash"""
    if not is_admin_check(message.from_user.id):
        return

    await state.set_state(CreateTestState.waiting_for_title)
    await message.answer(
        "📝 <b>Yangi test nomini kiriting:</b>\n"
        "<i>(Masalan: 9-sinflar uchun Matematika 1-oylik test)</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(CreateTestState.waiting_for_title, F.text)
async def process_test_title(message: Message, state: FSMContext):
    """Test nomini qabul qilish"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Test yaratish bekor qilindi.", reply_markup=get_admin_main_keyboard())
        return

    title = message.text.strip()
    await state.update_data(title=title)
    await state.set_state(CreateTestState.waiting_for_duration)
    await message.answer(
        f"Test nomi: <b>{title}</b>\n\n"
        "⏱ Test uchun necha daqiqa vaqt ajratilsin?\n"
        "<i>(Faqat butun son kiriting, masalan: 30)</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )


@router.message(CreateTestState.waiting_for_duration, F.text)
async def process_test_duration(message: Message, state: FSMContext):
    """Test vaqtini qabul qilish"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Test yaratish bekor qilindi.", reply_markup=get_admin_main_keyboard())
        return

    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Iltimos, faqat musbat butun son kiriting! (Masalan: 30)")
        return

    duration = int(text)
    await state.update_data(duration=duration)
    await state.set_state(CreateTestState.waiting_for_questions)

    help_text = (
        "📥 <b>Endi test savollarini yuboring!</b>\n\n"
        "Savollarni 2 xil usulda yuklashingiz mumkin:\n\n"
        "<b>1-usul: Matn ko'rinishida yuborish:</b>\n"
        "<i>1. O'zbekiston poytaxti qaysi?\n"
        "A) Samarqand\n"
        "B) Toshkent\n"
        "C) Buxoro\n"
        "D) Xiva\n"
        "Javob: B\n"
        "===\n"
        "2. 5 * 5 nechiga teng?\n"
        "A) 20\n"
        "B) 25\n"
        "C) 30\n"
        "D) 15\n"
        "Javob: B</i>\n\n"
        "<b>2-usul: Excel (.xlsx) fayl ko'rinishida yuborish:</b>\n"
        "To'ldirilgan faylni hujjat (document) sifatida botga yuboring."
    )
    await message.answer(help_text, reply_markup=get_cancel_keyboard(), parse_mode="HTML")


@router.message(CreateTestState.waiting_for_questions, F.text)
async def process_questions_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession
):
    """Savollarni matn ko'rinishida qabul qilish"""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Test yaratish bekor qilindi.", reply_markup=get_admin_main_keyboard())
        return

    questions, errors = parse_questions_from_text(message.text)

    if errors:
        error_msg = "⚠️ <b>Savollarni qabul qilishda quyidagi xatoliklar aniqlandi:</b>\n\n"
        error_msg += "\n".join(f"• {e}" for e in errors[:10])
        if len(errors) > 10:
            error_msg += f"\n... va yana {len(errors) - 10} ta xato."
        error_msg += "\n\nIltimos, formatni tekshirib qaytadan yuboring."
        await message.answer(error_msg, parse_mode="HTML")
        return

    if not questions:
        await message.answer("⚠️ Hech qanday savol aniqlanmadi. Formatni tekshirib qaytadan yuboring.")
        return

    data = await state.get_data()
    title = data["title"]
    duration = data["duration"]

    # Testni bazada yaratish
    test = await create_test(
        session=session,
        title=title,
        duration_minutes=duration,
        created_by=message.from_user.id
    )

    # Savollarni testga qo'shish
    added_count = await add_questions_bulk(session, test.id, questions)
    await state.clear()

    manage_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Testni ko'rish va boshqarish", callback_data=f"admin_manage_test:{test.id}")],
        ]
    )

    await message.answer(
        f"✅ <b>Test muvaffaqiyatli yaratildi va darhol faollashtirildi!</b>\n\n"
        f"📖 Nomi: <b>{test.title}</b>\n"
        f"⏱ Vaqti: <b>{test.duration_minutes} daqiqa</b>\n"
        f"❓ Savollar soni: <b>{added_count} ta</b>\n"
        f"Holati: 🟢 <b>Faol (barcha o'quvchilarga ochiq!)</b>\n\n"
        f"Endi barcha o'quvchilar «📝 Testlar» bo'limida ushbu testni ko'rishlari va topshirishlari mumkin.",
        reply_markup=manage_kb,
        parse_mode="HTML"
    )


@router.message(CreateTestState.waiting_for_questions, F.document)
async def process_questions_excel(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot
):
    """Savollarni fayl ko'rinishida (.xlsx, .txt, .csv) qabul qilish"""
    doc = message.document
    filename = (doc.file_name or "").lower()

    if not (filename.endswith(".xlsx") or filename.endswith(".xls") or filename.endswith(".txt") or filename.endswith(".csv")):
        await message.answer("⚠️ Iltimos, Bloknot (.txt) yoki Excel (.xlsx) faylini yuboring!")
        return

    file = await bot.get_file(doc.file_id)
    file_bytes_io = io.BytesIO()
    await bot.download_file(file.file_path, file_bytes_io)
    file_bytes = file_bytes_io.getvalue()

    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        questions, errors = parse_questions_from_excel(file_bytes)
    else:
        text_content = file_bytes.decode("utf-8-sig", errors="replace")
        questions, errors = parse_questions_from_text(text_content)

    if errors:
        error_msg = "⚠️ <b>Faylda quyidagi xatoliklar aniqlandi:</b>\n\n"
        error_msg += "\n".join(f"• {e}" for e in errors[:10])
        if len(errors) > 10:
            error_msg += f"\n... va yana {len(errors) - 10} ta xato."
        error_msg += "\n\nIltimos, faylni to'g'rilab qaytadan yuboring."
        await message.answer(error_msg, parse_mode="HTML")
        return

    if not questions:
        await message.answer("⚠️ Faylda savollar topilmadi. Shablon asosida to'ldirilganiga ishonch hosil qiling.")
        return

    data = await state.get_data()
    title = data["title"]
    duration = data["duration"]

    test = await create_test(
        session=session,
        title=title,
        duration_minutes=duration,
        created_by=message.from_user.id
    )

    added_count = await add_questions_bulk(session, test.id, questions)
    await state.clear()

    manage_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Testni ko'rish va boshqarish", callback_data=f"admin_manage_test:{test.id}")],
        ]
    )

    await message.answer(
        f"✅ <b>Test fayldan muvaffaqiyatli yaratildi va darhol faollashtirildi!</b>\n\n"
        f"📖 Nomi: <b>{test.title}</b>\n"
        f"⏱ Vaqti: <b>{test.duration_minutes} daqiqa</b>\n"
        f"❓ Yuklangan savollar: <b>{added_count} ta</b>\n"
        f"Holati: 🟢 <b>Faol (barcha o'quvchilarga ochiq!)</b>\n\n"
        f"Endi barcha o'quvchilar «📝 Testlar» bo'limida ushbu testni ko'rishlari va topshirishlari mumkin.",
        reply_markup=manage_kb,
        parse_mode="HTML"
    )


# ==================== TESTLARNI BOSHQARISH ====================

@router.message(F.text == "📋 Testlarni boshqarish")
async def show_admin_tests(message: Message, session: AsyncSession):
    """Mavjud testlar ro'yxati va ularni boshqarish"""
    if not is_admin_check(message.from_user.id):
        return

    tests = await get_all_tests(session)
    if not tests:
        await message.answer(
            "📭 Hozircha hech qanday test yaratilmagan.\n"
            "«➕ Yangi test yaratish» tugmasi orqali yangi test qo'shishingiz mumkin."
        )
        return

    text = (
        "📋 <b>Barcha testlar ro'yxati (ON / OFF boshqaruvi):</b>\n\n"
        "🟢 <b>[ON]</b> — Test ochiq (O'quvchilar testni yechishi mumkin)\n"
        "🔴 <b>[OFF]</b> — Test yopiq (O'quvchilarga ko'rinmaydi va yopiladi)\n\n"
        "💡 <i>Testni darhol yoqish yoki o'chirish uchun o'ng tarafdagi [ON / OFF] tugmasini bosing:</i>"
    )
    await message.answer(text, reply_markup=get_admin_tests_list_keyboard(tests), parse_mode="HTML")


@router.callback_query(F.data == "admin_tests_back")
async def admin_tests_back_callback(callback: CallbackQuery, session: AsyncSession):
    """Testlar ro'yxatiga qaytish"""
    tests = await get_all_tests(session)
    if not tests:
        await callback.message.edit_text("Hozircha hech qanday test yaratilmagan.")
        return

    text = (
        "📋 <b>Barcha testlar ro'yxati (ON / OFF boshqaruvi):</b>\n\n"
        "🟢 <b>[ON]</b> — Test ochiq (O'quvchilar testni yechishi mumkin)\n"
        "🔴 <b>[OFF]</b> — Test yopiq (O'quvchilarga ko'rinmaydi va yopiladi)\n\n"
        "💡 <i>Testni darhol yoqish yoki o'chirish uchun o'ng tarafdagi [ON / OFF] tugmasini bosing:</i>"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_tests_list_keyboard(tests), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_manage_test:"))
async def manage_single_test_callback(callback: CallbackQuery, session: AsyncSession):
    """Bitta testning tafsilotlari va boshqaruv menyusi"""
    await callback.answer()
    test_id = int(callback.data.split(":")[1])
    test = await get_test(session, test_id)
    if not test:
        await callback.message.answer("Test topilmadi!")
        return

    status_str = "🟢 ON (Ochiq - O'quvchilar topshirishi mumkin)" if test.is_active else "🔴 OFF (Yopiq - O'quvchilarga ko'rinmaydi)"
    attempts_count = len(test.attempts) if test.attempts else 0

    text = (
        f"📖 <b>Test:</b> {test.title}\n"
        f"⏱ <b>Davomiyligi:</b> {test.duration_minutes} daqiqa\n"
        f"❓ <b>Savollar soni:</b> {len(test.questions)} ta\n"
        f"👥 <b>Topshirganlar soni:</b> {attempts_count} nafar\n"
        f"📌 <b>Holati:</b> {status_str}\n\n"
        "Kerakli amalni tanlang:"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_test_control_keyboard(test), parse_mode="HTML")


@router.callback_query(F.data.startswith("toggle_test:"))
async def toggle_test_status_callback(callback: CallbackQuery, session: AsyncSession):
    """Testni ON / OFF qilish"""
    parts = callback.data.split(":")
    test_id = int(parts[1])
    new_status = bool(int(parts[2]))

    test = await set_test_active_status(session, test_id, new_status)
    if not test:
        await callback.answer("Test topilmadi!", show_alert=True)
        return

    action_text = f"🟢 «{test.title}» testi YOQILDI (ON)!" if new_status else f"🔴 «{test.title}» testi O'CHIRILDI (OFF)!"
    await callback.answer(action_text, show_alert=True)

    curr_text = callback.message.text or ""
    if "ro'yxati" in curr_text or "Barcha testlar" in curr_text:
        tests = await get_all_tests(session)
        text = (
            "📋 <b>Barcha testlar ro'yxati (ON / OFF boshqaruvi):</b>\n\n"
            "🟢 <b>[ON]</b> — Test ochiq (O'quvchilar testni yechishi mumkin)\n"
            "🔴 <b>[OFF]</b> — Test yopiq (O'quvchilarga ko'rinmaydi va yopiladi)\n\n"
            "💡 <i>Testni darhol yoqish yoki o'chirish uchun o'ng tarafdagi [ON / OFF] tugmasini bosing:</i>"
        )
        await callback.message.edit_text(text, reply_markup=get_admin_tests_list_keyboard(tests), parse_mode="HTML")
    else:
        status_str = "🟢 ON (Ochiq - O'quvchilar topshirishi mumkin)" if test.is_active else "🔴 OFF (Yopiq - O'quvchilarga ko'rinmaydi)"
        attempts_count = len(test.attempts) if test.attempts else 0
        text = (
            f"📖 <b>Test:</b> {test.title}\n"
            f"⏱ <b>Davomiyligi:</b> {test.duration_minutes} daqiqa\n"
            f"❓ <b>Savollar soni:</b> {len(test.questions)} ta\n"
            f"👥 <b>Topshirganlar soni:</b> {attempts_count} nafar\n"
            f"📌 <b>Holati:</b> {status_str}\n\n"
            "Kerakli amalni tanlang:"
        )
        await callback.message.edit_text(text, reply_markup=get_admin_test_control_keyboard(test), parse_mode="HTML")


# ==================== NATIJALAR VA REYTING ====================

@router.callback_query(F.data.startswith("leaderboard:"))
async def view_leaderboard_callback(callback: CallbackQuery, session: AsyncSession):
    """Test natijalarini reyting ko'rinishida chatga chiqarish"""
    await callback.answer()
    test_id = int(callback.data.split(":")[1])
    test = await get_test(session, test_id)
    if not test:
        await callback.message.answer("Test topilmadi!")
        return

    attempts = await get_test_leaderboard(session, test_id)
    if not attempts:
        await callback.message.answer("Hozircha hech kim ushbu testni topshirmagan.")
        return

    lines = [f"🏆 <b>«{test.title}» bo'yicha TOP natijalar:</b>\n"]
    for idx, att in enumerate(attempts[:20], start=1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        student_name = att.user.full_name if att.user else "Noma'lum"
        grade = att.user.grade if att.user else ""
        lines.append(
            f"{medal} <b>{student_name}</b> ({grade})\n"
            f"   └ Natija: <b>{att.score}/{att.total_questions}</b> ({att.percentage:.1f}%)"
        )

    if len(attempts) > 20:
        lines.append(f"\n<i>... va yana {len(attempts) - 20} nafar o'quvchi. To'liq ro'yxatni Excel fayl orqali yuklab oling.</i>")

    await callback.message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data.startswith("export_excel:"))
async def export_excel_callback(callback: CallbackQuery, session: AsyncSession):
    """Test natijalarini Excel fayl ko'rinishida generatsiya qilib yuborish"""
    test_id = int(callback.data.split(":")[1])
    test = await get_test(session, test_id)
    if not test:
        await callback.answer("Test topilmadi!", show_alert=True)
        return

    attempts = await get_test_leaderboard(session, test_id)
    if not attempts:
        await callback.answer("⚠️ Hozircha hech kim ushbu testni topshirmagan.", show_alert=True)
        return

    await callback.answer("Fayllar tayyorlanmoqda...")
    clean_title = "".join(c for c in test.title if c.isalnum() or c in (" ", "_", "-")).strip()

    # 1. Chiroyli formatlangan Excel (.xlsx) fayli
    stream_xlsx = generate_results_excel(test.title, attempts)
    doc_xlsx = BufferedInputFile(stream_xlsx.getvalue(), filename=f"Natijalar_{clean_title}.xlsx")
    await callback.message.answer_document(
        document=doc_xlsx,
        caption=(
            f"📊 <b>«{test.title}» — Excel (.xlsx) hisoboti</b>\n\n"
            f"👥 Jami qatnashchilar: <b>{len(attempts)} nafar</b>\n"
            f"💡 <i>Eslatma: Ushbu .xlsx faylni Microsoft Excel, WPS Office yoki Google Sheets (Google Jadvallar) orqali oching.</i>"
        ),
        parse_mode="HTML"
    )

    # 2. CSV (.csv) fayli - Agar kompyuteringizda Excel o'rnatilmagan bo'lsa, Bloknotda ham bemalol ochiladi
    stream_csv = generate_results_csv(test.title, attempts)
    doc_csv = BufferedInputFile(stream_csv.getvalue(), filename=f"Natijalar_{clean_title}.csv")
    await callback.message.answer_document(
        document=doc_csv,
        caption=(
            f"📄 <b>«{test.title}» — CSV (.csv) matnli jadvali</b>\n"
            f"<i>(Agar kompyuteringizda Excel bo'lmasa, ushbu faylni Bloknotda to'g'ridan-to'g'ri o'qishingiz mumkin)</i>"
        ),
        parse_mode="HTML"
    )


# ==================== TESTNI O'CHIRISH ====================

@router.callback_query(F.data.startswith("confirm_delete:"))
async def confirm_delete_callback(callback: CallbackQuery):
    """Testni o'chirishni tasdiqlash so'rovi"""
    test_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "⚠️ <b>DIQQAT!</b>\n\n"
        "Haqiqatan ham ushbu testni va barcha o'quvchilar natijalarini o'chirib tashlamoqchimisiz?\n"
        "Bu amalni ortga qaytarib bo'lmaydi!",
        reply_markup=get_confirm_delete_keyboard(test_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("do_delete:"))
async def do_delete_callback(callback: CallbackQuery, session: AsyncSession):
    """Testni butunlay o'chirish"""
    test_id = int(callback.data.split(":")[1])
    success = await delete_test(session, test_id)
    if success:
        await callback.answer("Test muvaffaqiyatli o'chirildi!", show_alert=True)
    else:
        await callback.answer("Test topilmadi!", show_alert=True)

    tests = await get_all_tests(session)
    if not tests:
        await callback.message.edit_text("Barcha testlar o'chirildi. Hozirda testlar mavjud emas.")
        return

    text = "📋 <b>Barcha testlar ro'yxati:</b>\n\nBoshqarish uchun testni tanlang:"
    await callback.message.edit_text(text, reply_markup=get_admin_tests_list_keyboard(tests), parse_mode="HTML")
