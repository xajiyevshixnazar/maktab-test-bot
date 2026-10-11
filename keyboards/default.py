from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_student_main_keyboard() -> ReplyKeyboardMarkup:
    """O'quvchilar uchun menyu: Faqat test topshirish va o'z natijalari"""
    keyboard = [
        [
            KeyboardButton(text="📝 Testlar"),
            KeyboardButton(text="📊 Natijalarim"),
        ],
        [
            KeyboardButton(text="👤 Profilim"),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        persistent=True,
    )


def get_admin_main_keyboard() -> ReplyKeyboardMarkup:
    """Ustoz (Admin) uchun asosiy menyu: Faqat testlarni yaratish va boshqarish"""
    keyboard = [
        [
            KeyboardButton(text="➕ Yangi test yaratish"),
            KeyboardButton(text="📋 Testlarni boshqarish"),
        ],
        [
            KeyboardButton(text="📄 Excel shablon olish"),
            KeyboardButton(text="👤 Ustoz profili"),
        ],
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        persistent=True,
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Amalni bekor qilish klaviaturasi"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
