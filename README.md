# 📚 Maktab Oylik Test Telegram Boti

Ushbu bot maktab o'quvchilaridan oylik test sinovlarini avtomatlashtirilgan tarzda olish, natijalarni hisoblash, vaqtni nazorat qilish va reyting hisobotlarini Excel (.xlsx) formatida shakllantirish uchun yaratilgan to'liq asinxron tizimdir.

---

## 🛠 Texnologiyalar

- **Dasturlash tili:** Python 3.12+
- **Telegram Bot Framework:** Aiogram 3.x (Asinxron FSM, Routers, Middlewares)
- **ORM / Ma'lumotlar bazasi:** SQLAlchemy 2.0 (Async) + `asyncpg` (PostgreSQL / Supabase) yoki `aiosqlite` (SQLite)
- **Excel bilan ishlash:** `openpyxl` (Shablon yaratish, savollarni o'qish, natijalarni chiroyli jadvallarda eksport qilish)
- **Konfiguratsiya:** `python-dotenv`

---

## 🗄 Ma'lumotlar Bazasi Strukturasi (Database Schema)

Loyiha ma'lumotlar bazasi quyidagi 5 ta asosiy jadvaldan iborat:

### 1. `users` (Foydalanuvchilar)
- `id` (BigInteger, Primary Key) — Telegram User ID
- `full_name` (String) — O'quvchining Ism va Familiyasi
- `grade` (String) — Sinf yoki guruh (masalan: `9-A`, `11-B`)
- `role` (String) — Foydalanuvchi roli (`student` yoki `admin`)
- `created_at` (DateTime) — Ro'yxatdan o'tgan vaqti

### 2. `tests` (Testlar)
- `id` (Integer, Primary Key, Auto Increment) — Test ID si
- `title` (String) — Test nomi (masalan: `Oktabr oyi Matematika testi`)
- `description` (Text, ixtiyoriy) — Test haqida qo'shimcha ma'lumot
- `duration_minutes` (Integer) — Test davomiyligi (daqiqa hisobida)
- `is_active` (Boolean) — Testning faollik holati (`True` bo'lsa o'quvchilar ko'radi)
- `created_by` (BigInteger, FK -> users.id) — Testni yaratgan ustoz
- `created_at` (DateTime) — Yaratilgan vaqti

### 3. `questions` (Savollar)
- `id` (Integer, Primary Key, Auto Increment) — Savol ID si
- `test_id` (Integer, FK -> tests.id, On Delete Cascade) — Qaysi testga tegishliligi
- `question_text` (Text) — Savol matni
- `option_a` (Text) — A varianti matni
- `option_b` (Text) — B varianti matni
- `option_c` (Text) — C varianti matni
- `option_d` (Text) — D varianti matni
- `correct_option` (String: 'A', 'B', 'C', 'D') — To'g'ri javob kaliti

### 4. `test_attempts` (Topshirish urinishlari)
- `id` (Integer, Primary Key, Auto Increment) — Urinish ID si
- `test_id` (Integer, FK -> tests.id) — Test ID si
- `user_id` (BigInteger, FK -> users.id) — O'quvchi Telegram ID si
- `started_at` (DateTime) — Test boshlangan vaqti
- `finished_at` (DateTime) — Test yakunlangan vaqti
- `is_completed` (Boolean) — Yakunlanganlik belgisi
- `score` (Integer) — To'g'ri javoblar soni
- `total_questions` (Integer) — Jami savollar soni
- `percentage` (Float) — To'plangan foiz (masalan: `85.0%`)
- **Unique Constraint (`test_id`, `user_id`)**: Har bir o'quvchi bitta testni faqat 1 marta topshirishini ta'minlaydi!

### 5. `student_answers` (O'quvchi javoblari jurnali)
- `id` (Integer, Primary Key)
- `attempt_id` (Integer, FK -> test_attempts.id, On Delete Cascade)
- `question_id` (Integer, FK -> questions.id)
- `selected_option` (String) — O'quvchi tanlagan variant
- `is_correct` (Boolean) — To'g'ri yoki noto'g'riligi

---

## 📁 Loyiha Kataloglar Tuzilishi

```text
maktab uchun bot/
│
├── config.py                 # Sozlamalar va .env ni yuklash
├── main.py                   # Botni ishga tushiruvchi markaziy fayl
├── requirements.txt          # Kerakli Python kutubxonalari
├── .env                      # Token va maxfiy ma'lumotlar
├── .env.example              # Namuna konfiguratsiya
│
├── database/                 # Ma'lumotlar bazasi qatlami
│   ├── connection.py         # SQLAlchemy asinxron sessiyalar va engine
│   ├── models.py             # Jadvallar modellari (ORM)
│   └── crud.py               # Ma'lumotlarni o'qish/yozish funksiyalari
│
├── handlers/                 # Telegram hodisalarini qabul qiluvchilar
│   ├── common.py             # /start, Ro'yxatdan o'tish (FSM), Profil
│   ├── student.py            # Test ishlash, savollarni chiqarish, taymer
│   └── admin.py              # Test yaratish, faollashtirish, Excel eksport
│
├── keyboards/                # Tugmalar
│   ├── default.py            # Asosiy menyu (Reply) tugmalari
│   └── inline.py             # Test tanlash, A/B/C/D inline tugmalari
│
├── middlewares/              # O'rta qatlam dasturlari
│   └── db_session.py         # Har bir so'rovga DB sessiyasini yetkazuvchi
│
├── states/                   # Aiogram FSM holatlari
│   ├── registration.py       # Ro'yxatdan o'tish holatlari
│   ├── test_taking.py        # Test yechish holati
│   └── admin_states.py       # Test yaratish holati
│
└── utils/                    # Qo'shimcha yordamchilar
    ├── excel_helper.py       # Excel shablon, import va reyting eksporti
    ├── question_parser.py    # Matnli savollarni tahlil qilish (Regex parser)
    └── timer.py              # Test uchun orqa fonda asinxron taymer
```

---

## 🚀 O'rnatish va Ishga Tushirish

### 1. Virtual muhitni faollashtirish va kutubxonalarni o'rnatish

```bash
# Virtual muhit yaratish (agar yaratilmagan bo'lsa)
python -m venv venv

# Virtual muhitni yoqish (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Kutubxonalarni o'rnatish
pip install -r requirements.txt
```

### 2. `.env` faylini sozlash

`.env` faylini oching va quyidagi ma'lumotlarni kiriting:

```env
# 1. Telegram boti tokeni (@BotFather orqali olinadi)
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz

# 2. Ustoz (Admin) Telegram ID raqami (o'z ID ingizni bilish uchun @userinfobot dan foydalaning)
ADMIN_IDS=123456789

# 3. Ma'lumotlar bazasi:
# Lokal SQLite ishlatish uchun (avtomatik yaratiladi, qo'shimcha sozlash shart emas):
DATABASE_URL=sqlite+aiosqlite:///school_test.db

# YOKI PostgreSQL (Supabase) ishlatish uchun:
# DATABASE_URL=postgresql+asyncpg://postgres:parolingiz@db.loyiha_id.supabase.co:5432/postgres
```

### 3. Botni ishga tushirish

```bash
python main.py
```

---

## 🎯 Botdan Foydalanish Qo'llanmasi

### 👨‍🏫 Ustoz (Admin) uchun:

1. Botga `/start` yoki `/admin` buyrug'ini yuboring.
2. **«⚙️ Ustoz paneli»** ga kiring:
   - **➕ Yangi test yaratish**:
     - Test nomi (masalan: `9-A sinf Biologiya 1-oy`)
     - Test vaqti (masalan: `25` minut)
     - Savollarni yuklash:
       - **1-usul (Matn orqali):**
         ```text
         1. O'simlik hujayrasida fotosintez qayerda sodir bo'ladi?
         A) Yadroda
         B) Xloroplastda
         C) Mitoxondriyada
         D) Ribosomada
         Javob: B
         ===
         2. DNK qayerda saqlanadi?
         A) Sitoplazmada
         B) Yadroda
         C) Qobiqda
         D) Vakuolada
         Javob: B
         ```
       - **2-usul (Excel orqali):** «📄 Excel shablon olish» tugmasini bosing, yuklab olingan shablonni to'ldirib botga yuboring.
   - **📋 Testlarni boshqarish**:
     - Testni **🟢 Faollashtirish** yoki **🔴 To'xtatish**.
     - **📊 Natijalar / Reyting** — eng yuqori ball to'plagan o'quvchilarni chatda ko'rish.
     - **📥 Excel yuklab olish** — barcha o'quvchilar natijalarini to'liq formatlangan Excel faylida yuklab olish.
     - **🗑 Testni o'chirish**.

---

### 🎒 O'quvchi uchun:

1. Botga kirib `/start` tugmasini bosadi.
2. Ism, familiya va sinfini kiritadi (masalan: *Sardor Rahimov*, *9-B*).
3. **«📝 Testlar»** tugmasini bosadi:
   - Ustoz faollashtirgan testlar ro'yxati chiqadi.
   - Test tanlangach uning savollar soni va vaqti ko'rsatiladi.
4. **«🚀 Testni boshlash»** bosilganda:
   - Savollar bittalab chiqadi.
   - Savollar va variantlar (A, B, C, D) tasodifiy (random) aralashtirib beriladi.
   - Ajratilgan vaqt tugasa yoki barcha savollar yechilsa, test yopiladi.
   - O'quvchiga umumiy natija: to'g'ri, noto'g'ri javoblar va foiz ko'rsatiladi.
   - Testni **faqat 1 marta** topshirish mumkin (qayta topshirish bloklangan).
