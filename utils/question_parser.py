import re
from typing import List, Dict, Any, Tuple

OPT_CHARS = r"A-Da-dАБВГДСабвгдс"


def normalize_option_char(char: str, has_cyrillic_be: bool = False) -> str:
    """
    Harfni (lotin yoki kirill) standart lotin A, B, C, D ga o'tkazish.
    has_cyrillic_be=True bo'lsa (ya'ni matnda 'Б' varianti mavjud bo'lsa),
    kirill alifbosi tartibi ishlatiladi: А->A, Б->B, В->C, Г->D.
    Aks holda (kirillcha ko'rinishdosh/homoglyph harflar): А->A, В->B, С->C, Д->D.
    """
    if not char:
        return ""
    ch = char.strip()
    ch_upper = ch.upper()
    if ch_upper in ("A", "B", "C", "D"):
        return ch_upper

    if has_cyrillic_be:
        mapping = {
            "А": "A", "а": "A",
            "Б": "B", "б": "B",
            "В": "C", "в": "C",
            "Г": "D", "г": "D",
            "Д": "D", "д": "D",
            "С": "C", "с": "C",
        }
    else:
        mapping = {
            "А": "A", "а": "A",
            "В": "B", "в": "B",
            "С": "C", "с": "C",
            "Д": "D", "д": "D",
            "Г": "D", "г": "D",
            "Б": "B", "б": "B",
        }
    return mapping.get(ch, mapping.get(ch_upper, ch_upper))


def parse_questions_from_text(raw_text: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    O'qituvchilar tomonidan kiritiladigan barcha turdagi test formatlarini
    aqlli va universal tahlil qilish (parse qilish).
    PDF, Word, Bloknot yoki matn ko'rinishida yuborilgan barcha fayllarni
    hamda lotin va kirill yozuvidagi variantlarni to'liq qo'llab-quvvatlaydi.

    Qo'llab-quvvatlanadigan formatlar:
    1. Raqamlangan savollar (1., 2., 3...) + Oxirida "Javoblar kaliti" bloki (1-A, 2-D, 3-C...)
    2. Variantlar qatorda xohlagancha joylashishi mumkin:
       - Har biri alohida qatorda (A... B... C... D...)
       - Bir qatorda 2 tadan (A... B... va C... D...)
       - Barchasi 1 qatorda (A... B... C... D...)
    3. Har bir savol tagida alohida "Javob: B" yozilgan formatlar.
    4. Savollar orasida "===" yoki bo'sh qatorlar bilan ajratilgan formatlar.
    """
    errors: List[str] = []
    questions: List[Dict[str, Any]] = []

    if not raw_text:
        return [], ["Matn bo'sh! Iltimos, test savollarini yuboring."]

    # Belgilarni tozalash (Windows / PDF xos belgilari)
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\xa0", " ").replace("\u200b", "").replace("\ufeff", "").replace("\xad", "")
    text = text.strip()

    if not text:
        return [], ["Matn bo'sh! Iltimos, test savollarini yuboring."]

    # Kirillcha 'Б' yoki 'б' harfi variant markerida ishlatilganligini aniqlash
    has_cyrillic_be = bool(
        re.search(r"(?:^|[\s\n\(])(?:\()?([Бб])[\)\.\:\-]|[\d]+[\-\.\:\)]\s*[Бб]", text)
    )

    # =========================================================================
    # 1-BOSQICH: Javoblar kalitini (Answer Keys) aniqlash
    # =========================================================================
    keys: Dict[int, str] = {}

    # 1.1 "Javoblar kaliti", "Kalitlar", "Javoblar", "Answers", "Ответы", "Ключи" kabi bloklarni topish
    key_block_pattern = re.compile(
        r"(?:javoblar\s*kaliti|жавоблар\s*калити|javoblar\s*ro['`]?yxati|kalitlar|калитлар|javoblar|жавоблар|answers|kalit|калит|ответы|ключи|ключ)\s*[:\-]?(.*)$",
        re.IGNORECASE | re.DOTALL
    )
    key_match = key_block_pattern.search(text)

    body_text = text
    if key_match:
        key_content = key_match.group(1)
        body_text = text[:key_match.start()].strip()
        # "1-A, 2-D, 3-C" yoki "1.A 2.D" kabi barcha juftliklarni ajratib olish
        found_keys = re.findall(rf"(\d+)\s*[\-\.\:\)]\s*([{OPT_CHARS}])", key_content)
        for num_str, letter in found_keys:
            keys[int(num_str)] = normalize_option_char(letter, has_cyrillic_be)

    # 1.2 Agar sarlavha bo'lmasa, matnning eng oxiridagi kalitlar qatorlarini tekshirish
    if not keys:
        lines = [line.strip() for line in body_text.splitlines() if line.strip()]
        key_lines = []
        while lines:
            last_line = lines[-1]
            matches = re.findall(rf"\b(\d+)\s*[\-\.\:\)]\s*([{OPT_CHARS}])\b", last_line)
            # Agar qatorda kamida 2 ta kalit juftligi bo'lsa yoki qator butunlay kalitlardan iborat bo'lsa
            if len(matches) >= 2 or (len(matches) == 1 and re.match(rf"^\d+\s*[\-\.\:\)]\s*[{OPT_CHARS}]$", last_line)):
                key_lines.insert(0, last_line)
                lines.pop()
            else:
                break
        if key_lines:
            combined_key_text = " ".join(key_lines)
            found_keys = re.findall(rf"\b(\d+)\s*[\-\.\:\)]\s*([{OPT_CHARS}])\b", combined_key_text)
            for num_str, letter in found_keys:
                keys[int(num_str)] = normalize_option_char(letter, has_cyrillic_be)
            body_text = "\n".join(lines).strip()

    # =========================================================================
    # 2-BOSQICH: Savollarni raqamlari bo'yicha ajratish (1., 2., 3...)
    # =========================================================================
    # Har bir savol qator boshidagi raqam bilan boshlanadi: masalan "1. ", "2. ", "1) "
    question_split_pattern = re.compile(r"(?:^|\n)\s*(\d+)[\.\)\:\-]\s+")
    parts = question_split_pattern.split(body_text)

    # Agar raqamlar bo'yicha kamida 1 ta savol topilsa (parts uzunligi >= 3)
    if len(parts) >= 3:
        for i in range(1, len(parts), 2):
            q_num = int(parts[i])
            q_body = parts[i + 1].strip()
            if not q_body:
                continue

            # Variantlar markerlarini qidirish: A), B), C), D) (yoki (A), A., A:)
            opt_pattern = re.compile(rf"(?:^|[\s\n\(])(?:\()?([{OPT_CHARS}])[\)\.\:\-]\s*")
            opt_matches = list(opt_pattern.finditer(q_body))

            if len(opt_matches) < 4:
                errors.append(f"{q_num}-savolda barcha variantlar (A, B, C, D) to'liq topilmadi.")
                continue

            # Birinchi variant boshlanishidan oldingi qism — bu savol matni!
            first_opt = opt_matches[0]
            q_text = q_body[:first_opt.start()].strip()
            # Boshidagi qoldiqlarni tozalash
            q_text = re.sub(r"^\d+[\.\)\:\-]\s*", "", q_text).strip()
            # Qator ko'chishlarini chiroyli bitta matnga aylantirish
            q_text = re.sub(r"\s*\n\s*", " ", q_text)

            opts: Dict[str, str] = {}
            letters_found: List[Tuple[str, str]] = []

            for idx in range(len(opt_matches)):
                m = opt_matches[idx]
                raw_letter = m.group(1)
                norm_letter = normalize_option_char(raw_letter, has_cyrillic_be)
                start_pos = m.end()
                end_pos = opt_matches[idx + 1].start() if idx + 1 < len(opt_matches) else len(q_body)
                opt_content = q_body[start_pos:end_pos].strip()

                # Agar variant oxirida "Javob: B" yoki "Kalit: B" yozilgan bo'lsa, tozalaymiz
                inline_ans_match = re.search(
                    rf"(?:javob|kalit|to['`]?g['`]?ri\s*javob|answer|жавоб|калит|тўғри\s*жавоб|ответ)\s*[:\-]?\s*([{OPT_CHARS}])",
                    opt_content,
                    re.IGNORECASE
                )
                if inline_ans_match:
                    if q_num not in keys:
                        keys[q_num] = normalize_option_char(inline_ans_match.group(1), has_cyrillic_be)
                    opt_content = opt_content[:inline_ans_match.start()].strip()

                # Qatorlarni tozalash
                opt_content = re.sub(r"\s*\n\s*", " ", opt_content)
                opts[norm_letter] = opt_content
                letters_found.append((norm_letter, opt_content))

            # Agar variant harflari A, B, C, D ga to'liq tushmagan bo'lsa (lekin 4 ta variant bo'lsa)
            if not (opts.get("A") and opts.get("B") and opts.get("C") and opts.get("D")):
                if len(letters_found) >= 4:
                    opts["A"] = letters_found[0][1]
                    opts["B"] = letters_found[1][1]
                    opts["C"] = letters_found[2][1]
                    opts["D"] = letters_found[3][1]

            # To'g'ri javobni aniqlash
            correct = keys.get(q_num)
            if not correct:
                errors.append(f"{q_num}-savolning to'g'ri javobi (kaliti) topilmadi.")
                continue

            if not (opts.get("A") and opts.get("B") and opts.get("C") and opts.get("D")):
                errors.append(f"{q_num}-savolda A, B, C, D variantlarining matni to'liq emas.")
                continue

            questions.append({
                "question_text": q_text,
                "option_a": opts["A"],
                "option_b": opts["B"],
                "option_c": opts["C"],
                "option_d": opts["D"],
                "correct_option": correct,
            })

        return questions, errors

    # =========================================================================
    # 3-BOSQICH: Agar raqamlar bo'lmasa — Blokli format (=== yoki bo'sh qator)
    # =========================================================================
    if "===" in body_text:
        blocks = [b.strip() for b in body_text.split("===") if b.strip()]
    else:
        blocks = [b.strip() for b in re.split(r"\n\s*\n", body_text) if b.strip()]

    for idx, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        q_text = ""
        opt_a = ""
        opt_b = ""
        opt_c = ""
        opt_d = ""
        correct = keys.get(idx, "")

        opt_pattern = re.compile(rf"^(?:\()?([{OPT_CHARS}])[\)\.\:\-]\s*(.*)$")
        ans_pattern = re.compile(rf"^(?:javob|kalit|to['`]?g['`]?ri\s*javob|answer|жавоб|калит|тўғри\s*жавоб|ответ)\s*[\:\-]?\s*([{OPT_CHARS}])", re.IGNORECASE)

        question_lines = []
        parsing_options = False

        for line in lines:
            ans_match = ans_pattern.search(line)
            if ans_match:
                correct = normalize_option_char(ans_match.group(1), has_cyrillic_be)
                continue

            opt_match = opt_pattern.match(line)
            if opt_match:
                parsing_options = True
                raw_letter = opt_match.group(1)
                letter = normalize_option_char(raw_letter, has_cyrillic_be)
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

        q_text = " ".join(question_lines).strip()
        q_text = re.sub(r"^\d+[\)\.\:\-]\s*", "", q_text)

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
