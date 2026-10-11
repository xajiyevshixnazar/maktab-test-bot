import asyncio
import io
from database.connection import init_db, async_session_maker
from database.crud import (
    register_user,
    get_user,
    create_test,
    add_questions_bulk,
    get_test,
    set_test_active_status,
    start_test_attempt,
    record_answer,
    finish_test_attempt,
    get_test_leaderboard,
)
from utils.question_parser import parse_questions_from_text
from utils.excel_helper import (
    create_excel_template,
    parse_questions_from_excel,
    generate_results_excel,
)


async def run_tests():
    print("--- 1. Ma'lumotlar bazasini initsializatsiya qilish ---")
    await init_db()
    print("Database init muvaffaqiyatli!")

    print("\n--- 2. Matndan savollarni tahlil qilish testi ---")
    sample_text = """
    1. O'zbekiston poytaxti qaysi shahar?
    A) Samarqand
    B) Toshkent
    C) Buxoro
    D) Xiva
    Javob: B
    ===
    2. 12 * 12 nechiga teng?
    A) 144
    B) 124
    C) 134
    D) 154
    Javob: A
    """
    questions, errors = parse_questions_from_text(sample_text)
    assert len(errors) == 0, f"Xatoliklar bor: {errors}"
    assert len(questions) == 2, f"Kutilgan savollar soni 2, lekin {len(questions)} ta"
    assert questions[0]["correct_option"] == "B"
    assert questions[1]["correct_option"] == "A"
    print("Matn parseri a'lo darajada ishladi!")

    print("\n--- 3. Excel shablon yaratish va o'qish testi ---")
    template_stream = create_excel_template()
    parsed_excel_questions, excel_errors = parse_questions_from_excel(template_stream.getvalue())
    assert len(excel_errors) == 0, f"Excel parsing xatosi: {excel_errors}"
    assert len(parsed_excel_questions) == 3, f"Shablondagi 3 ta namuna savol o'qilmadi: {len(parsed_excel_questions)}"
    print(f"Excel shablon yaratildi va {len(parsed_excel_questions)} ta namuna savol muvaffaqiyatli o'qildi!")

    print("\n--- 4. CRUD va foydalanuvchilar oqimi testi ---")
    async with async_session_maker() as session:
        # User 1: Admin
        admin = await register_user(session, user_id=111, full_name="Ustoz Olimov", grade="Ustoz", role="admin")
        # User 2: O'quvchi
        student = await register_user(session, user_id=222, full_name="Ali Valiyev", grade="9-A", role="student")
        # User 3: O'quvchi 2
        student2 = await register_user(session, user_id=333, full_name="Zilola Karimova", grade="9-A", role="student")

        # Test yaratish
        test = await create_test(
            session=session,
            title="Matematika 1-oylik test",
            duration_minutes=30,
            created_by=admin.id
        )
        assert test.id is not None
        assert test.is_active is False

        # Savollarni yuklash
        added = await add_questions_bulk(session, test.id, questions)
        assert added == 2

        # Testni faollashtirish
        test = await set_test_active_status(session, test.id, True)
        assert test.is_active is True

        # O'quvchi 1 testni topshiradi
        att1 = await start_test_attempt(session, test_id=test.id, user_id=student.id, total_questions=2)
        await record_answer(session, att1.id, questions[0].get("id", 1), "B", True)
        await record_answer(session, att1.id, questions[1].get("id", 2), "A", True)
        att1 = await finish_test_attempt(session, att1.id, score=2, percentage=100.0)

        # O'quvchi 2 testni topshiradi
        att2 = await start_test_attempt(session, test_id=test.id, user_id=student2.id, total_questions=2)
        await record_answer(session, att2.id, questions[0].get("id", 1), "B", True)
        await record_answer(session, att2.id, questions[1].get("id", 2), "B", False)
        att2 = await finish_test_attempt(session, att2.id, score=1, percentage=50.0)

        # Reytingni olish
        leaderboard = await get_test_leaderboard(session, test.id)
        assert len(leaderboard) == 2
        assert leaderboard[0].user.full_name == "Ali Valiyev"
        assert leaderboard[0].score == 2
        assert leaderboard[1].user.full_name == "Zilola Karimova"
        assert leaderboard[1].score == 1
        print("CRUD, javoblar qaydi va reyting tizimi 100% to'g'ri ishladi!")

        # Excel natijalar hisobotini yaratish
        excel_report = generate_results_excel(test.title, leaderboard)
        assert excel_report.getbuffer().nbytes > 1000
        print(f"Excel natijalar hisoboti muvaffaqiyatli yaratildi ({excel_report.getbuffer().nbytes} bayt)!")

    print("\n==========================================")
    print("BARCHA TESTLAR MUVAFFAQIYATLI O'TDI!")
    print("==========================================")


if __name__ == "__main__":
    asyncio.run(run_tests())
