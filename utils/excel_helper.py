import io
from datetime import datetime
from typing import List, Dict, Any, Tuple
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def create_excel_template() -> io.BytesIO:
    """O'qituvchi uchun savollar kiritish shablon faylini (.xlsx) yaratish"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Savollar"

    # Sarlavhalar
    headers = [
        "№",
        "Savol matni",
        "A varianti",
        "B varianti",
        "C varianti",
        "D varianti",
        "To'g'ri javob (A/B/C/D)"
    ]

    # Namuna ma'lumotlar
    sample_rows = [
        [1, "O'zbekiston Respublikasi mustaqillikka qachon erishgan?", "1989-yil", "1991-yil", "1992-yil", "1993-yil", "B"],
        [2, "Toshkent shahri qaysi davlat poytaxti?", "Qozog'iston", "Tojikiston", "O'zbekiston", "Qirg'iziston", "C"],
        [3, "5 * (12 - 4) ifodaning qiymatini toping.", "40", "35", "45", "50", "A"]
    ]

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    for row_data in sample_rows:
        ws.append(row_data)

    # Qatorlarni formatlash
    for row in ws.iter_rows(min_row=2, max_row=len(sample_rows) + 1, min_col=1, max_col=len(headers)):
        for cell in row:
            cell.border = thin_border
            if cell.column in [1, 7]:  # № va To'g'ri javob ustunlari o'rtada
                cell.alignment = center_align

    # Ustun kengliklarini avtomatik to'g'rilash
    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 50
    ws.column_dimensions['C'].width = 25
    ws.column_dimensions['D'].width = 25
    ws.column_dimensions['E'].width = 25
    ws.column_dimensions['F'].width = 25
    ws.column_dimensions['G'].width = 24

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def parse_questions_from_excel(file_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Excel fayldan savollarni o'qib olish"""
    errors = []
    questions = []

    try:
        wb = openpyxl.load_workbook(filename=io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
    except Exception as e:
        return [], [f"Excel faylini ochishda xatolik yuz berdi: {str(e)}"]

    row_idx = 1
    for row in ws.iter_rows(values_only=True):
        if row_idx == 1:
            row_idx += 1
            continue  # Sarlavha qatorini o'tkazib yuboramiz

        row_idx += 1
        if not row or not any(row):
            continue

        # Ustunlar indeksi:
        # 0: № (ixtiyoriy)
        # 1: Savol matni
        # 2: Variant A
        # 3: Variant B
        # 4: Variant C
        # 5: Variant D
        # 6: To'g'ri javob (A, B, C, D)
        if len(row) < 7:
            errors.append(f"{row_idx - 1}-qatorda ma'lumotlar ustuni yetarli emas (kamida 7 ta ustun bo'lishi kerak).")
            continue

        q_text = str(row[1]).strip() if row[1] is not None else ""
        opt_a = str(row[2]).strip() if row[2] is not None else ""
        opt_b = str(row[3]).strip() if row[3] is not None else ""
        opt_c = str(row[4]).strip() if row[4] is not None else ""
        opt_d = str(row[5]).strip() if row[5] is not None else ""
        raw_correct = str(row[6]).strip().upper() if row[6] is not None else ""

        if not q_text:
            continue  # Bo'sh qator deb hisoblaymiz

        if not (opt_a and opt_b and opt_c and opt_d):
            errors.append(f"{row_idx - 1}-qatordagi savolning barcha 4 ta varianti to'liq kiritilmagan.")
            continue

        if raw_correct not in ["A", "B", "C", "D"]:
            errors.append(f"{row_idx - 1}-qatorda to'g'ri javob xato kiritilgan: '{raw_correct}'. Faqat A, B, C yoki D bo'lishi kerak.")
            continue

        questions.append({
            "question_text": q_text,
            "option_a": opt_a,
            "option_b": opt_b,
            "option_c": opt_c,
            "option_d": opt_d,
            "correct_option": raw_correct,
        })

    return questions, errors


def generate_results_excel(test_title: str, attempts: list) -> io.BytesIO:
    """O'quvchilar natijalarini chiroyli formatlangan Excel faylga eksport qilish"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Natijalar"

    # Sarlavha bloki
    ws.merge_cells("A1:I1")
    title_cell = ws["A1"]
    title_cell.value = f"«{test_title}» TEST NATIJALARI"
    title_cell.font = Font(name="Calibri", size=14, bold=True, color="1F497D")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    # Ustun sarlavhalari
    headers = [
        "№",
        "O'quvchi F.I.Sh",
        "Sinf / Guruh",
        "To'g'ri javob",
        "Noto'g'ri javob",
        "Jami savollar",
        "Natija (%)",
        "Boshlagan vaqti",
        "Yakunlagan vaqti"
    ]
    ws.append([])  # Bo'sh qator
    ws.append(headers)

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='CCCCCC'),
        right=Side(style='thin', color='CCCCCC'),
        top=Side(style='thin', color='CCCCCC'),
        bottom=Side(style='thin', color='CCCCCC')
    )

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=3, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align

    # Ma'lumotlarni yozish
    row_num = 4
    for idx, att in enumerate(attempts, start=1):
        full_name = att.user.full_name if att.user else "Noma'lum"
        grade = att.user.grade if att.user else "-"
        incorrect = att.total_questions - att.score
        pct_str = f"{att.percentage:.1f}%"
        start_str = att.started_at.strftime("%Y-%m-%d %H:%M") if att.started_at else "-"
        finish_str = att.finished_at.strftime("%Y-%m-%d %H:%M") if att.finished_at else "-"

        row_data = [
            idx,
            full_name,
            grade,
            att.score,
            incorrect,
            att.total_questions,
            pct_str,
            start_str,
            finish_str
        ]
        ws.append(row_data)

        # Rang va chegaralash
        is_even = (idx % 2 == 0)
        row_fill = PatternFill(start_color="F9FAFB" if is_even else "FFFFFF", fill_type="solid")

        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_num, column=col_idx)
            cell.border = thin_border
            cell.fill = row_fill
            if col_idx in [1, 3, 4, 5, 6, 7, 8, 9]:
                cell.alignment = center_align

        row_num += 1

    # Ustun kengliklari
    col_widths = {
        'A': 6,
        'B': 28,
        'C': 15,
        'D': 14,
        'E': 14,
        'F': 14,
        'G': 14,
        'H': 18,
        'I': 18,
    }
    for col, width in col_widths.items():
        ws.column_dimensions[col].width = width

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def generate_results_csv(test_title: str, attempts: list) -> io.BytesIO:
    """Natijalarni CSV formatida generatsiya qilish (Bloknot va istalgan matn muharririda to'g'ri ochilishi uchun)"""
    import csv
    string_io = io.StringIO()
    writer = csv.writer(string_io, delimiter=',', quoting=csv.QUOTE_MINIMAL)
    
    writer.writerow([f"Test: {test_title}"])
    writer.writerow(["№", "O'quvchi F.I.Sh", "Sinf / Guruh", "To'g'ri javob", "Noto'g'ri javob", "Jami savollar", "Natija (%)", "Boshlagan vaqti", "Yakunlagan vaqti"])
    
    for idx, att in enumerate(attempts, start=1):
        full_name = att.user.full_name if att.user else "Noma'lum"
        grade = att.user.grade if att.user else "-"
        incorrect = att.total_questions - att.score
        pct_str = f"{att.percentage:.1f}%"
        start_str = att.started_at.strftime("%Y-%m-%d %H:%M") if att.started_at else "-"
        finish_str = att.finished_at.strftime("%Y-%m-%d %H:%M") if att.finished_at else "-"
        writer.writerow([idx, full_name, grade, att.score, incorrect, att.total_questions, pct_str, start_str, finish_str])
        
    bytes_io = io.BytesIO(string_io.getvalue().encode('utf-8-sig'))
    bytes_io.seek(0)
    return bytes_io
