from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Test, Question, TestAttempt, StudentAnswer


# ==================== FOYDALANUVCHI (USER) ====================

async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    """ID bo'yicha foydalanuvchini olish"""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def register_user(
    session: AsyncSession,
    user_id: int,
    full_name: str,
    grade: str,
    role: str = "student"
) -> User:
    """Foydalanuvchini ro'yxatdan o'tkazish yoki ma'lumotlarini yangilash"""
    user = await get_user(session, user_id)
    if user:
        user.full_name = full_name
        user.grade = grade
        user.role = role
    else:
        user = User(
            id=user_id,
            full_name=full_name,
            grade=grade,
            role=role,
        )
        session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_role(session: AsyncSession, user_id: int, role: str) -> Optional[User]:
    """Foydalanuvchi rolini o'zgartirish (masalan, admin qilish)"""
    user = await get_user(session, user_id)
    if user:
        user.role = role
        await session.commit()
        await session.refresh(user)
    return user


# ==================== TESTLAR ====================

async def create_test(
    session: AsyncSession,
    title: str,
    duration_minutes: int,
    created_by: int,
    description: Optional[str] = None
) -> Test:
    """Yangi test yaratish"""
    test = Test(
        title=title,
        description=description,
        duration_minutes=duration_minutes,
        created_by=created_by,
        is_active=True,
    )
    session.add(test)
    await session.commit()
    await session.refresh(test)
    return test


async def get_test(session: AsyncSession, test_id: int) -> Optional[Test]:
    """Testni ID orqali olish (savollari va urinishlari bilan birga)"""
    stmt = (
        select(Test)
        .where(Test.id == test_id)
        .options(
            selectinload(Test.questions),
            selectinload(Test.attempts),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_tests(session: AsyncSession) -> List[Test]:
    """Barcha testlar ro'yxatini olish"""
    stmt = (
        select(Test)
        .options(
            selectinload(Test.questions),
            selectinload(Test.attempts),
        )
        .order_by(Test.id.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_active_tests(session: AsyncSession) -> List[Test]:
    """Hozirda faol bo'lgan testlarni olish"""
    stmt = (
        select(Test)
        .where(Test.is_active == True)
        .options(
            selectinload(Test.questions),
            selectinload(Test.attempts),
        )
        .order_by(Test.id.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def set_test_active_status(session: AsyncSession, test_id: int, is_active: bool) -> Optional[Test]:
    """Test holatini faol / nofaol ga o'zgartirish"""
    test = await get_test(session, test_id)
    if test:
        test.is_active = is_active
        await session.commit()
    return test


async def delete_test(session: AsyncSession, test_id: int) -> bool:
    """Testni va unga tegishli hamma ma'lumotlarni o'chirish"""
    test = await session.get(Test, test_id)
    if test:
        await session.delete(test)
        await session.commit()
        return True
    return False


# ==================== SAVOLLAR ====================

async def add_questions_bulk(
    session: AsyncSession,
    test_id: int,
    questions_data: List[dict]
) -> int:
    """Testga bir nechta savollarni birdaniga qo'shish"""
    questions = [
        Question(
            test_id=test_id,
            question_text=q["question_text"],
            option_a=q["option_a"],
            option_b=q["option_b"],
            option_c=q["option_c"],
            option_d=q["option_d"],
            correct_option=q["correct_option"].upper(),
        )
        for q in questions_data
    ]
    session.add_all(questions)
    await session.commit()
    return len(questions)


async def get_questions_for_test(session: AsyncSession, test_id: int) -> List[Question]:
    """Testga tegishli savollarni olish"""
    stmt = select(Question).where(Question.test_id == test_id).order_by(Question.id.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ==================== TEST TOPSHIRISH (ATTEMPT) ====================

async def get_attempt(
    session: AsyncSession,
    test_id: int,
    user_id: int
) -> Optional[TestAttempt]:
    """O'quvchining ushbu test bo'yicha urinishini tekshirish"""
    stmt = (
        select(TestAttempt)
        .where(TestAttempt.test_id == test_id, TestAttempt.user_id == user_id)
        .options(selectinload(TestAttempt.answers))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def start_test_attempt(
    session: AsyncSession,
    test_id: int,
    user_id: int,
    total_questions: int
) -> TestAttempt:
    """O'quvchi testni boshlaganda urinish qaydini yaratish"""
    attempt = TestAttempt(
        test_id=test_id,
        user_id=user_id,
        total_questions=total_questions,
        is_completed=False,
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return attempt


async def record_answer(
    session: AsyncSession,
    attempt_id: int,
    question_id: int,
    selected_option: str,
    is_correct: bool
) -> StudentAnswer:
    """O'quvchining savolga bergan javobini saqlash"""
    answer = StudentAnswer(
        attempt_id=attempt_id,
        question_id=question_id,
        selected_option=selected_option.upper(),
        is_correct=is_correct,
    )
    session.add(answer)
    await session.commit()
    return answer


async def finish_test_attempt(
    session: AsyncSession,
    attempt_id: int,
    score: int,
    percentage: float
) -> Optional[TestAttempt]:
    """Testni yakunlash va natijani yozish"""
    attempt = await session.get(TestAttempt, attempt_id)
    if attempt:
        attempt.is_completed = True
        attempt.finished_at = datetime.utcnow()
        attempt.score = score
        attempt.percentage = round(percentage, 2)
        await session.commit()
        await session.refresh(attempt)
    return attempt


async def get_test_leaderboard(
    session: AsyncSession,
    test_id: int
) -> List[TestAttempt]:
    """Test bo'yicha barcha topshirgan o'quvchilar natijalarini reyting tartibida olish"""
    stmt = (
        select(TestAttempt)
        .where(TestAttempt.test_id == test_id, TestAttempt.is_completed == True)
        .options(selectinload(TestAttempt.user))
        .order_by(TestAttempt.score.desc(), TestAttempt.finished_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_user_attempts(
    session: AsyncSession,
    user_id: int
) -> List[TestAttempt]:
    """O'quvchining barcha topshirgan testlari tarixi"""
    stmt = (
        select(TestAttempt)
        .where(TestAttempt.user_id == user_id)
        .options(selectinload(TestAttempt.test))
        .order_by(TestAttempt.id.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
