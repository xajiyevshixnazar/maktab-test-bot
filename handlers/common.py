import re
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

import config
from database.crud import get_user, register_user
from keyboards.default import (
    get_student_main_keyboard,
    get_admin_main_keyboard,
)
from states.registration import RegistrationState

router = Router(name="common_router")


def is_admin_check(user_id: int) -> bool:
    """Faqatgina .env dagi ADMIN_IDS ro'yxatida bo'lganlar admin (ustoz) hisoblanadi"""
    return user_id in config.ADMIN_IDS


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):
    """Botga start berilganda: Ustoz va O'quvchini darhol ajratish"""
    await state.clear()
    user_id = message.from_user.id

    # 1. AGAR FOYDALANUVCHI USTOZ (ADMIN) BO'LSA:
    if is_admin_check(user_id):
        user = await get_user(session, user_id)
        if not user:
            user = await register_user(
                session=session,
                user_id=user_id,
                full_name=message.from_user.full_name or "Ustoz",
                grade="Ustoz",
                role="admin"
            )
        welcome_text = (
            f"Assalomu alaykum, Ustoz <b>{user.full_name}</b>!\n\n"
            "👨‍🏫 <b>Ustoz boshqaruv paneliga xush kelibsiz.</b>\n"
            "Siz bu yerda yangi oylik testlar yaratishingiz, ularni boshqarishingiz va o'quvchilar natijalarini olishingiz mumkin:"
        )
        await message.answer(
            welcome_text,
            reply_markup=get_admin_main_keyboard(),
            parse_mode="HTML"
        )
        return

    # 2. AGAR ODDIY O'QUVCHI BO'LSA:
    user = await get_user(session, user_id)
    if not user:
        # Yangi o'quvchi - Ro'yxatdan o'tish
        await state.set_state(RegistrationState.waiting_for_full_name)
        await message.answer(
            "Assalomu alaykum! Maktab oylik test tizimiga xush kelibsiz.\n\n"
            "Iltimos, testlarda qatnashish uchun <b>Ism va Familiyangizni</b> kiriting:\n"
            "<i>(Masalan: Saidov Jasur)</i>",
            parse_mode="HTML"
        )
        return

    welcome_text = (
        f"Assalomu alaykum, <b>{user.full_name}</b>!\n"
        f"Sinf / Guruh: <b>{user.grade}</b>\n\n"
        "Oylik testlar tizimiga xush kelibsiz. Quyidagi menyudan kerakli bo'limni tanlang:"
    )
    await message.answer(
        welcome_text,
        reply_markup=get_student_main_keyboard(),
        parse_mode="HTML"
    )


# ==================== RO'YXATDAN O'TISH (FSM - FAQAT O'QUVCHILAR UCHUN) ====================

@router.message(RegistrationState.waiting_for_full_name, F.text)
async def process_full_name(message: Message, state: FSMContext):
    """Ism-familiyani qabul qilish"""
    full_name = message.text.strip()
    if len(full_name.split()) < 2:
        await message.answer(
            "⚠️ Iltimos, ism va familiyangizni to'liq kiriting!\n"
            "<i>(Masalan: Karimov Anvar)</i>",
            parse_mode="HTML"
        )
        return

    await state.update_data(full_name=full_name)
    await state.set_state(RegistrationState.waiting_for_grade)
    await message.answer(
        f"Rahmat, <b>{full_name}</b>!\n\n"
        "Endi esa <b>sinfingizni harfi bilan birga</b> kiriting:\n"
        "<i>(Masalan: <b>10-A</b>, <b>10-B</b>, <b>9-A</b> yoki <b>11-C</b>)</i>\n\n"
        "⚠️ <i>Diqqat: Faqat raqamning o'zini kiritish mumkin emas (masalan, shunchaki '10' emas).</i>",
        parse_mode="HTML"
    )


@router.message(RegistrationState.waiting_for_grade, F.text)
async def process_grade(message: Message, state: FSMContext, session: AsyncSession):
    """Sinfni qabul qilish - sinf raqami va harfi bo'lishi shart"""
    raw_grade = message.text.strip()

    # Masalan: 10-A, 10A, 10 a, 9-b, 11-V, 7-A
    match = re.match(r"^([1-9]|1[0-1])[\s\-_]*([A-Za-zА-Яа-яЎўҚқҒғҲҳ])$", raw_grade)

    if not match:
        await message.answer(
            "⚠️ <b>Sinf noto'g'ri kiritildi!</b>\n\n"
            "Maktabda bir nechta parallel sinflar (A, B, C, D...) bo'lganligi sababli, "
            "<b>sinf raqami va harfini</b> birgalikda kiritishingiz shart.\n\n"
            "<i>To'g'ri namunalar:</i>\n"
            "• <b>10-A</b>\n"
            "• <b>10-B</b>\n"
            "• <b>9-A</b>\n"
            "• <b>11-C</b>\n\n"
            "Iltimos, sinfingizni to'g'ri formatda qaytadan kiriting:",
            parse_mode="HTML"
        )
        return

    # Standart ko'rinishga keltirish (masalan: 10-A)
    grade_num = match.group(1)
    grade_letter = match.group(2).upper()
    formatted_grade = f"{grade_num}-{grade_letter}"

    data = await state.get_data()
    full_name = data.get("full_name")
    user_id = message.from_user.id

    await register_user(session, user_id=user_id, full_name=full_name, grade=formatted_grade, role="student")
    await state.clear()

    await message.answer(
        f"✅ <b>Tabriklaymiz, siz muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\n\n"
        f"👤 F.I.Sh: <b>{full_name}</b>\n"
        f"🏫 Sinf: <b>{formatted_grade}</b>\n\n"
        "Endi ustozingiz testni faollashtirganda testlarni topshirishingiz mumkin.",
        reply_markup=get_student_main_keyboard(),
        parse_mode="HTML"
    )


# ==================== BEKOR QILISH ====================

@router.message(F.text == "❌ Bekor qilish")
async def cmd_cancel(message: Message, state: FSMContext):
    """Amalni bekor qilish"""
    await state.clear()
    is_admin = is_admin_check(message.from_user.id)
    kb = get_admin_main_keyboard() if is_admin else get_student_main_keyboard()
    await message.answer("Amal bekor qilindi.", reply_markup=kb)


# ==================== PROFIL VA TAHRIRLASH ====================

@router.message(F.text.in_(["👤 Profilim", "👤 Ustoz profili"]))
async def show_profile(message: Message, session: AsyncSession):
    """Foydalanuvchi profili"""
    user_id = message.from_user.id
    user = await get_user(session, user_id)
    if not user:
        await message.answer("Siz ro'yxatdan o'tmagansiz. /start buyrug'ini bosing.")
        return

    is_admin = is_admin_check(user_id)
    joined_date = user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else "Noma'lum"
    status_label = "Ustoz (Admin)" if is_admin else "O'quvchi"

    text = (
        f"👤 <b>Sizning profilingiz:</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📝 F.I.Sh: <b>{user.full_name}</b>\n"
        f"🏫 Sinf / Guruh: <b>{user.grade}</b>\n"
        f"📅 Qo'shilgan sana: <b>{joined_date}</b>\n"
        f"👑 Status: <b>{status_label}</b>"
    )

    # Agar o'quvchi bo'lsa, ma'lumotlarini (masalan sinfini) tahrirlash tugmasini chiqaramiz
    if not is_admin:
        edit_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✏️ Ism va Sinfni o'zgartirish", callback_data="edit_my_profile")]
            ]
        )
        await message.answer(text, reply_markup=edit_kb, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "edit_my_profile")
async def edit_profile_callback(callback: CallbackQuery, state: FSMContext):
    """O'quvchi ma'lumotlarini qayta kiritishni boshlash"""
    await callback.answer()
    await state.set_state(RegistrationState.waiting_for_full_name)
    await callback.message.answer(
        "📝 Iltimos, yangi <b>Ism va Familiyangizni</b> kiriting:\n"
        "<i>(Masalan: Saidov Jasur)</i>",
        parse_mode="HTML"
    )
