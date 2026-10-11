from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import Test


def get_active_tests_keyboard(tests: list[Test]) -> InlineKeyboardMarkup:
    """O'quvchi uchun faol testlar ro'yxati inline tugmalari"""
    buttons = []
    for t in tests:
        q_count = len(t.questions)
        btn_text = f"📝 {t.title} ({q_count} savol, {t.duration_minutes} daqiqa)"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"student_select_test:{t.id}")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_start_test_confirm_keyboard(test_id: int) -> InlineKeyboardMarkup:
    """Testni boshlashni tasdiqlash tugmalari"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Testni boshlash", callback_data=f"start_test:{test_id}")],
            [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="cancel_test_select")],
        ]
    )


def get_question_options_keyboard(question_index: int, options_letters: list[str]) -> InlineKeyboardMarkup:
    """
    Savol variantlari (A, B, C, D) inline tugmalari.
    options_letters: ['A', 'B', 'C', 'D']
    """
    row = [
        InlineKeyboardButton(
            text=f"🔘 {letter}",
            callback_data=f"ans:{question_index}:{letter}"
        )
        for letter in options_letters
    ]
    return InlineKeyboardMarkup(inline_keyboard=[row])


def get_admin_tests_list_keyboard(tests: list[Test]) -> InlineKeyboardMarkup:
    """Ustoz uchun barcha testlar ro'yxati: test nomi va bitta bosishda ON/OFF qiluvchi tugma"""
    buttons = []
    for t in tests:
        status_btn = "🟢 [ON - Ochiq]" if t.is_active else "🔴 [OFF - Yopiq]"
        toggle_action = f"toggle_test:{t.id}:{0 if t.is_active else 1}"
        buttons.append([
            InlineKeyboardButton(text=f"📖 {t.title}", callback_data=f"admin_manage_test:{t.id}"),
            InlineKeyboardButton(text=status_btn, callback_data=toggle_action),
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_test_control_keyboard(test: Test) -> InlineKeyboardMarkup:
    """Bitta testni boshqarish menyusi (ON/OFF, excel, reyting, o'chirish)"""
    if test.is_active:
        toggle_text = "🔴 TESTNI YOPISH (OFF QILISH)"
        toggle_action = f"toggle_test:{test.id}:0"
    else:
        toggle_text = "🟢 TESTNI OCHISH (ON QILISH)"
        toggle_action = f"toggle_test:{test.id}:1"

    keyboard = [
        [InlineKeyboardButton(text=toggle_text, callback_data=toggle_action)],
        [
            InlineKeyboardButton(text="📊 Natijalar / Reyting", callback_data=f"leaderboard:{test.id}"),
            InlineKeyboardButton(text="📥 Excel yuklab olish", callback_data=f"export_excel:{test.id}"),
        ],
        [InlineKeyboardButton(text="🗑 Testni butunlay o'chirish", callback_data=f"confirm_delete:{test.id}")],
        [InlineKeyboardButton(text="⬅️ Testlar ro'yxatiga qaytish", callback_data="admin_tests_back")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirm_delete_keyboard(test_id: int) -> InlineKeyboardMarkup:
    """Testni o'chirishni tasdiqlash"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 Ha, butunlay o'chirish", callback_data=f"do_delete:{test_id}"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"admin_manage_test:{test_id}"),
            ]
        ]
    )
