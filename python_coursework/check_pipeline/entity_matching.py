from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher
import csv
import re
import zipfile
import xml.etree.ElementTree as ET

from .field_extractor import extract_from_pdf, extract_from_text
from .models import DocumentRecord
from .ocr_tesseract import extract_text_with_tesseract


TEXT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass
class ExpectedPayment:
    payment_id: str
    expected_amount: str
    expected_currency: str
    expected_payer_name: str
    expected_recipient_name: str
    expected_purpose: str
    expected_date: str
    expected_reference_code: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EntityMatchResult:
    payment_id: str
    status: str
    score: str
    matched_file: str
    expected_amount: str
    actual_amount: str
    expected_currency: str
    actual_currency: str
    expected_payer_name: str
    actual_payer_name: str
    expected_recipient_name: str
    actual_recipient_name: str
    expected_purpose: str
    expected_reference_code: str
    actual_reference: str
    amount_score: str
    recipient_score: str
    payer_score: str
    purpose_score: str
    date_score: str
    reference_score: str
    mismatch_reasons: str
    source_path: str

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_text(value: str) -> str:
    value = (value or "").upper().replace("Ё", "Е")
    value = re.sub(r"\b(ООО|ОАО|ЗАО|ИП|ЧУП|УП|ОДО|АО|LLC|LTD)\b", " ", value)
    value = re.sub(r"[^A-ZА-Я0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_code(value: str) -> str:
    return re.sub(r"[^A-ZА-Я0-9]+", "", (value or "").upper().replace("Ё", "Е"))


def parse_amount(value: str) -> float | None:
    match = re.search(r"-?\d+(?:[,.]\d+)?", value or "")
    if not match:
        return None
    return float(match.group(0).replace(",", "."))


def parse_date(value: str) -> datetime | None:
    value = value or ""
    for pattern in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        match = re.search(r"\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}", value)
        if not match:
            return None
        try:
            return datetime.strptime(match.group(0), pattern)
        except ValueError:
            continue
    return None


def string_similarity(left: str, right: str) -> float:
    left_norm = normalize_text(left)
    right_norm = normalize_text(right)
    if not left_norm and not right_norm:
        return 100.0
    if not left_norm or not right_norm:
        return 0.0
    direct = SequenceMatcher(None, left_norm, right_norm).ratio()
    left_tokens = " ".join(sorted(left_norm.split()))
    right_tokens = " ".join(sorted(right_norm.split()))
    token_sort = SequenceMatcher(None, left_tokens, right_tokens).ratio()
    return round(max(direct, token_sort) * 100, 2)


def amount_similarity(expected: str, actual: str) -> float:
    expected_value = parse_amount(expected)
    actual_value = parse_amount(actual)
    if expected_value is None or actual_value is None:
        return 0.0
    diff = abs(expected_value - actual_value)
    if diff <= 0.01:
        return 100.0
    if expected_value == 0:
        return 0.0
    relative = diff / abs(expected_value)
    return round(max(0.0, 100.0 - relative * 500.0), 2)


def date_similarity(expected: str, actual: str) -> float:
    expected_date = parse_date(expected)
    actual_date = parse_date(actual)
    if expected_date is None or actual_date is None:
        return 50.0 if not expected and not actual else 0.0
    days = abs((actual_date.date() - expected_date.date()).days)
    if days == 0:
        return 100.0
    if days <= 3:
        return 85.0
    if days <= 7:
        return 60.0
    return 20.0


def reference_similarity(expected: str, document: DocumentRecord) -> float:
    if not expected:
        return 100.0
    needle = normalize_code(expected)
    haystack = normalize_code(" ".join([document.reference, document.rrn, document.mcc_code, document.full_text]))
    if needle and needle in haystack:
        return 100.0
    return string_similarity(expected, document.full_text)


def purpose_similarity(expected: str, document: DocumentRecord) -> float:
    if not expected:
        return 100.0
    return string_similarity(expected, document.full_text)


def compare_expected_to_document(expected: ExpectedPayment, document: DocumentRecord) -> EntityMatchResult:
    amount_score = amount_similarity(expected.expected_amount, document.amount)
    recipient_score = string_similarity(expected.expected_recipient_name, document.recipient_name or document.full_text)
    payer_score = string_similarity(expected.expected_payer_name, document.payer_name or document.full_text) if expected.expected_payer_name else 100.0
    purpose_score = purpose_similarity(expected.expected_purpose, document)
    date_score = date_similarity(expected.expected_date, document.primary_datetime)
    reference_score = reference_similarity(expected.expected_reference_code, document)
    currency_score = 100.0 if not expected.expected_currency or expected.expected_currency == document.currency else 0.0

    total = (
        0.30 * amount_score
        + 0.20 * recipient_score
        + 0.15 * payer_score
        + 0.15 * purpose_score
        + 0.10 * date_score
        + 0.05 * reference_score
        + 0.05 * currency_score
    )
    total = round(total, 2)

    reasons: list[str] = []
    if amount_score < 95:
        reasons.append("сумма")
    if recipient_score < 60:
        reasons.append("получатель")
    if payer_score < 60:
        reasons.append("плательщик")
    if purpose_score < 45:
        reasons.append("назначение платежа")
    if date_score < 60:
        reasons.append("дата")
    if reference_score < 60:
        reasons.append("код платежа")
    if currency_score < 100:
        reasons.append("валюта")

    if amount_score < 95 or recipient_score < 60:
        status = "не оплачено"
    elif total >= 85:
        status = "оплачено"
    elif total >= 60:
        status = "возможное совпадение"
    else:
        status = "не оплачено"

    return EntityMatchResult(
        payment_id=expected.payment_id,
        status=status,
        score=f"{total:.2f}%",
        matched_file=document.file_name,
        expected_amount=expected.expected_amount,
        actual_amount=document.amount,
        expected_currency=expected.expected_currency,
        actual_currency=document.currency,
        expected_payer_name=expected.expected_payer_name,
        actual_payer_name=document.payer_name,
        expected_recipient_name=expected.expected_recipient_name,
        actual_recipient_name=document.recipient_name,
        expected_purpose=expected.expected_purpose,
        expected_reference_code=expected.expected_reference_code,
        actual_reference=document.reference or document.rrn or document.mcc_code,
        amount_score=f"{amount_score:.2f}%",
        recipient_score=f"{recipient_score:.2f}%",
        payer_score=f"{payer_score:.2f}%",
        purpose_score=f"{purpose_score:.2f}%",
        date_score=f"{date_score:.2f}%",
        reference_score=f"{reference_score:.2f}%",
        mismatch_reasons=", ".join(reasons) if reasons else "нет",
        source_path=document.source_path,
    )


def _get(row: dict[str, str], *names: str) -> str:
    aliases = {normalize_code(key): value for key, value in row.items()}
    for name in names:
        value = aliases.get(normalize_code(name), "")
        if value:
            return str(value).strip()
    return ""


def _row_to_expected(row: dict[str, str], index: int) -> ExpectedPayment:
    return ExpectedPayment(
        payment_id=_get(row, "payment_id", "id", "код платежа", "номер", "номер платежа") or f"PAY-{index:03d}",
        expected_amount=_get(row, "expected_amount", "amount", "сумма", "ожидаемая сумма"),
        expected_currency=_get(row, "expected_currency", "currency", "валюта") or "BYN",
        expected_payer_name=_get(row, "expected_payer_name", "payer", "плательщик", "контрагент"),
        expected_recipient_name=_get(row, "expected_recipient_name", "recipient", "получатель"),
        expected_purpose=_get(row, "expected_purpose", "purpose", "назначение", "назначение платежа"),
        expected_date=_get(row, "expected_date", "date", "дата", "дата платежа"),
        expected_reference_code=_get(row, "expected_reference_code", "reference", "код", "код платежа", "rrn", "mcc"),
    )


def read_expected_payments(path: str | Path) -> list[ExpectedPayment]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    elif suffix == ".xlsx":
        rows = _read_xlsx_rows(path)
    else:
        raise ValueError("Таблица ожидаемых платежей должна быть в формате CSV или XLSX")
    return [_row_to_expected(row, index) for index, row in enumerate(rows, start=1)]


def _read_xlsx_rows(path: Path) -> list[dict[str, str]]:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", ns):
                shared_strings.append("".join(node.text or "" for node in item.findall(".//a:t", ns)))

        sheet_name = "xl/worksheets/sheet1.xml"
        root = ET.fromstring(archive.read(sheet_name))
        table: list[list[str]] = []
        for row in root.findall(".//a:row", ns):
            values: list[str] = []
            current_col = 0
            for cell in row.findall("a:c", ns):
                ref = cell.attrib.get("r", "")
                col_letters = re.sub(r"[^A-Z]", "", ref)
                if col_letters:
                    col_index = 0
                    for char in col_letters:
                        col_index = col_index * 26 + ord(char) - ord("A") + 1
                    while current_col < col_index - 1:
                        values.append("")
                        current_col += 1
                value_node = cell.find("a:v", ns)
                value = value_node.text if value_node is not None and value_node.text else ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared_strings[int(value)]
                elif cell.attrib.get("t") == "inlineStr":
                    value = "".join(node.text or "" for node in cell.findall(".//a:t", ns))
                values.append(value)
                current_col += 1
            table.append(values)

    if not table:
        return []
    headers = [str(value).strip() for value in table[0]]
    return [{headers[index]: row[index] if index < len(row) else "" for index in range(len(headers))} for row in table[1:]]


def extract_document(path: str | Path) -> DocumentRecord:
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        return extract_from_pdf(path)
    if path.suffix.lower() in TEXT_EXTENSIONS:
        text = extract_text_with_tesseract(path)
        return extract_from_text(text, source_path=str(path), file_name=path.name)
    raise ValueError(f"Неподдерживаемый формат документа: {path.suffix}")


def match_expected_with_documents(expected_rows: list[ExpectedPayment], documents: list[DocumentRecord]) -> list[EntityMatchResult]:
    candidates: list[tuple[float, int, int, EntityMatchResult]] = []
    for expected_index, expected in enumerate(expected_rows):
        for document_index, document in enumerate(documents):
            result = compare_expected_to_document(expected, document)
            score = float(result.score.rstrip("%"))
            candidates.append((score, expected_index, document_index, result))

    candidates.sort(key=lambda item: item[0], reverse=True)
    used_expected: set[int] = set()
    used_documents: set[int] = set()
    results_by_expected: dict[int, EntityMatchResult] = {}

    for score, expected_index, document_index, result in candidates:
        if expected_index in used_expected or document_index in used_documents:
            continue
        if score < 45:
            continue
        used_expected.add(expected_index)
        used_documents.add(document_index)
        results_by_expected[expected_index] = result

    empty_document = DocumentRecord("", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "")
    for index, expected in enumerate(expected_rows):
        if index not in results_by_expected:
            result = compare_expected_to_document(expected, empty_document)
            result.status = "не оплачено"
            result.score = "0.00%"
            result.matched_file = ""
            result.mismatch_reasons = "документ не найден"
            results_by_expected[index] = result

    return [results_by_expected[index] for index in range(len(expected_rows))]
