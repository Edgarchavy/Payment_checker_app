from __future__ import annotations

from pathlib import Path
import csv
import re
import sys

from check_pipeline.entity_matching import extract_document
from check_pipeline.xlsx_writer import write_xlsx


ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "project_output_py" / "00_source_pdf"
OUT_DIR = ROOT / "project_output_py" / "02_reference"
OUT_XLSX = OUT_DIR / "demo_expected_payments_fuzzy.xlsx"
OUT_CSV = OUT_DIR / "demo_expected_payments_fuzzy.csv"


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def mutate_recipient(value: str, index: int) -> str:
    value = normalize_spaces(value)
    variants = [
        value.upper(),
        value.replace(" po ", " ПО ").replace("telefona", "телефона"),
        value.replace(":", " ").replace("  ", " "),
        value.lower(),
        value.replace("UNIVERSAM", "УНИВЕРСАМ"),
    ]
    return variants[index % len(variants)] or value


def mutate_payer(value: str, index: int) -> str:
    value = normalize_spaces(value)
    if not value:
        return ""
    parts = value.split()
    variants = [
        value.title(),
        value.upper(),
        " ".join(parts[:-1]) + " " + parts[-1][:4] + "." if len(parts) >= 2 else value,
        value.replace(" ", "  "),
    ]
    return variants[index % len(variants)]


def build_purpose(document, index: int) -> str:
    if document.reference:
        return f"Оплата по документу {document.reference}"
    if document.rrn:
        return f"Оплата банковского документа RRN {document.rrn}"
    if document.mcc_code:
        return f"Оплата услуги MCC {document.mcc_code}"
    if document.recipient_name:
        return f"Оплата услуги: {document.recipient_name}"
    return f"Оплата по выставленному платежу {index:03d}"


def mutate_reference(document, index: int) -> str:
    source = document.rrn or document.reference or document.mcc_code
    if not source:
        return ""
    if index % 5 == 1:
        return source.replace("0", "O", 1)
    if index % 5 == 2:
        return f" {source} "
    return source


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_paths = sorted(PDF_DIR.glob("*.pdf"))
    if not pdf_paths:
        print(f"No PDF files found in {PDF_DIR}", file=sys.stderr)
        raise SystemExit(1)

    headers = [
        "payment_id",
        "expected_amount",
        "expected_currency",
        "expected_payer_name",
        "expected_recipient_name",
        "expected_purpose",
        "expected_date",
        "expected_reference_code",
        "demo_note",
    ]
    rows = []

    for index, pdf_path in enumerate(pdf_paths, start=1):
        document = extract_document(pdf_path)
        amount = document.amount
        recipient = mutate_recipient(document.recipient_name, index)
        payer = mutate_payer(document.payer_name, index)
        purpose = build_purpose(document, index)
        reference = mutate_reference(document, index)
        note = "нечеткое совпадение: изменено написание реквизитов"

        if index == 5:
            amount = str(float(amount or "0") + 1).rstrip("0").rstrip(".")
            note = "демо-ошибка: сумма намеренно изменена"
        elif index == 10:
            recipient = "ДРУГОЙ ПОЛУЧАТЕЛЬ"
            note = "демо-ошибка: получатель намеренно изменен"
        elif index == 14:
            purpose = "Оплата по назначению без точного кода"
            reference = ""
            note = "нечеткое совпадение без кода платежа"

        rows.append([
            f"PAY-{index:03d}",
            amount,
            document.currency or "BYN",
            payer,
            recipient,
            purpose,
            document.primary_datetime[:10],
            reference,
            note,
        ])

    # Extra expected payment with no corresponding check.
    rows.append([
        f"PAY-{len(rows) + 1:03d}",
        "777.77",
        "BYN",
        "Тестовый плательщик",
        "Тестовый получатель",
        "Платеж без соответствующего PDF-чека",
        "10.05.2026",
        "NO-MATCH-001",
        "демо-строка: чек отсутствует",
    ])

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)

    write_xlsx(
        OUT_XLSX,
        [headers] + rows,
        widths={1: 14, 2: 16, 3: 12, 4: 34, 5: 42, 6: 46, 7: 16, 8: 24, 9: 44},
        title="Demo expected payments for fuzzy matching",
    )
    print(OUT_XLSX)
    print(OUT_CSV)


if __name__ == "__main__":
    main()
