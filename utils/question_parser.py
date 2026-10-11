import re
from typing import List, Dict, Any, Tuple


def parse_questions_from_text(raw_text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Admin tomonidan matn ko'rinishida yuborilgan savollarni tahlil qilish (parse qilish).
    
    Qo'llab-quvvatlanadigan format:
    1. O'zbekiston poytaxti qaysi?
    A) Samarqand
    B) Toshkent
    C) Buxoro
    D) Andijon
    Javob: B
    
    Savollar orasida "===" yoki bo'sh qator bo'lishi mumkin.
    """
    errors = []
    questions = []

    # Savollar bloklarini ajratish (bo'sh qatorlar yoki '===' orqali)
    # Avval "===" bo'yicha ajratib ko'ramiz
    if "===" in raw_text:
        blocks = [b.strip() for b in raw_text.split("===") if b.strip()]
    else:
        # Bo'sh qatorlar (ikki yoki undan ko'p newline) bilan ajratish
        blocks = [b.strip() for b in re.split(r"\n\s*\n", raw_text) if b.strip()]

    for idx, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        q_text = ""
        opt_a = ""
        opt_b = ""
        opt_c = ""
        opt_d = ""
        correct = ""

        opt_pattern = re.compile(r"^([A-Da-d])[\)\.\:\-]\s*(.*)$")
        ans_pattern = re.compile(r"^(?:javob|kalit|to['`]?g['`]?ri\s*javob|answer)\s*[\:\-]?\s*([A-Da-d])", re.IGNORECASE)

        # Savol matni birinchi qator(lar)da bo'ladi, variantlar boshlanguncha
        question_lines = []
        parsing_options = False

        for line in lines:
            ans_match = ans_pattern.search(line)
            if ans_match:
                correct = ans_match.group(1).upper()
                continue

            opt_match = opt_pattern.match(line)
            if opt_match:
                parsing_options = True
                letter = opt_match.group(1).upper()
                content = opt_match.group(2).strip()
                if letter == "A":
                    opt_a = content
                elif letter == "B":
                    opt_b = content
                elif letter == "C":
                    opt_c = content
                elif letter == "D":
                    opt_d = content
            elif not parsing_options:
                question_lines.append(line)

        # Savol matnini yig'ish va oldidagi tartib raqamini (masalan "1. ") tozalash
        q_text = " ".join(question_lines).strip()
        q_text = re.sub(r"^\d+[\)\.\:\-]\s*", "", q_text)

        # Tekshiruvlar
        if not q_text:
            errors.append(f"{idx}-savolda savol matni topilmadi.")
            continue
        if not (opt_a and opt_b and opt_c and opt_d):
            errors.append(f"{idx}-savolda barcha variantlar (A, B, C, D) to'liq emas.")
            continue
        if not correct or correct not in ["A", "B", "C", "D"]:
            errors.append(f"{idx}-savolda to'g'ri javob ko'rsatilmagan (Masalan: Javob: B).")
            continue

        questions.append({
            "question_text": q_text,
            "option_a": opt_a,
            "option_b": opt_b,
            "option_c": opt_c,
            "option_d": opt_d,
            "correct_option": correct,
        })

    return questions, errors
