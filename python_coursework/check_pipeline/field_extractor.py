from __future__ import annotations

from pathlib import Path
import re

from .models import DocumentRecord
from .pdf_text import get_receipt_text_from_pdf


def normalize_lines(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if line and line.strip()]


def join_lines(lines: list[str]) -> str:
    return " | ".join(normalize_lines(lines))


def get_receipt_type(full_text: str) -> str:
    if "ERIP" in full_text or "RRN:" in full_text:
        return "detailed_payment"
    if "ABOWD" in full_text:
        return "transfer_or_exchange"
    if "USD" in full_text or "Spotify" in full_text:
        return "foreign_card_payment"
    if re.search(r"\([0-9]{4}\)", full_text):
        return "card_payment"
    return "other"


def first_match(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else ""


def all_matches(text: str, pattern: str) -> list[str]:
    return [match.group(1) for match in re.finditer(pattern, text)]


def _value_after_label(lines: list[str], labels: list[str], stop_words: list[str] | None = None) -> str:
    stop_words = stop_words or []
    normalized_labels = [label.upper() for label in labels]
    for index, line in enumerate(lines):
        upper_line = line.upper()
        for label in normalized_labels:
            if label in upper_line:
                label_start = upper_line.find(label)
                tail = line[label_start + len(label):].strip(" :|-")
                if tail:
                    return tail.strip()
                buffer: list[str] = []
                for next_line in lines[index + 1:index + 4]:
                    next_upper = next_line.upper()
                    if any(stop.upper() in next_upper for stop in stop_words):
                        break
                    if re.fullmatch(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}.*", next_line):
                        break
                    buffer.append(next_line)
                return " ".join(buffer).strip()
    return ""


def guess_recipient(lines: list[str], receipt_type: str) -> str:
    label_value = _value_after_label(
        lines,
        ["Наименование получателя", "Получатель платежа", "Получатель"],
        ["Дата", "Rata", "Номер карты", "MCC", "Сумма", "Плательщик"],
    )
    if label_value:
        return label_value

    if receipt_type in {"card_payment", "foreign_card_payment", "transfer_or_exchange", "other"}:
        return lines[4] if len(lines) > 4 else ""
    if receipt_type == "detailed_payment":
        buffer: list[str] = []
        for line in lines[10:]:
            if line == "Дата":
                break
            if re.fullmatch(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}", line):
                break
            buffer.append(line)
        return " ".join(buffer).strip()
    return ""


def guess_payer(lines: list[str], receipt_type: str) -> str:
    label_value = _value_after_label(
        lines,
        ["Плательщик", "Плательщих", "Отправитель платежа"],
        ["Счет", "Счёт", "Сумма", "Наименование получателя", "Получатель"],
    )
    if label_value:
        return label_value

    if receipt_type == "detailed_payment":
        return lines[4] if len(lines) > 4 else ""
    if receipt_type == "transfer_or_exchange":
        return lines[11] if len(lines) > 11 else ""
    return ""


def extract_from_text_lines(lines: list[str], source_path: str, file_name: str) -> DocumentRecord:
    lines = normalize_lines(lines)
    full_text = " | ".join(lines)
    receipt_type = get_receipt_type(full_text)

    date_time = first_match(full_text, r"([0-9]{2}\.[0-9]{2}\.[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2})")
    amount = first_match(full_text, r"(-?[0-9]+(?:\.[0-9]+)?)\s+(?:BYN|USD|EUR|RUB)")
    currency = first_match(full_text, r"-?[0-9]+(?:\.[0-9]+)?\s+([A-Z]{3})")
    standalone_cards = [line for line in lines if re.fullmatch(r"[0-9]\.[0-9]{4}", line)]
    masked_card = standalone_cards[0] if standalone_cards else first_match(full_text, r"([0-9]\.[0-9]{4})")
    mcc_code = first_match(full_text, r"\(([0-9]{4})\)")
    if not mcc_code:
        standalone_codes = [line for line in lines if re.fullmatch(r"[0-9]{4}", line)]
        mcc_code = standalone_codes[0] if standalone_codes else ""

    ibans = list(dict.fromkeys(all_matches(full_text, r"(BY[0-9A-Z]{10,})")))
    rrn = first_match(full_text, r"RRN[: ]+([0-9]{6,})")
    authorization_code = first_match(full_text, r"Код авторизации \| ([0-9]{4,})")
    reference = first_match(full_text, r"(ABOWD[0-9]+)")
    recipient_name = guess_recipient(lines, receipt_type)
    payer_name = guess_payer(lines, receipt_type)

    return DocumentRecord(
        file_name=file_name,
        source_path=source_path,
        receipt_type=receipt_type,
        primary_datetime=date_time,
        amount=amount,
        currency=currency,
        recipient_name=recipient_name,
        payer_name=payer_name,
        masked_card=masked_card,
        mcc_code=mcc_code,
        iban_first=ibans[0] if len(ibans) > 0 else "",
        iban_second=ibans[1] if len(ibans) > 1 else "",
        rrn=rrn,
        authorization_code=authorization_code,
        reference=reference,
        full_text=full_text,
    )


def extract_from_text(text: str, source_path: str, file_name: str) -> DocumentRecord:
    return extract_from_text_lines(text.splitlines(), source_path=source_path, file_name=file_name)


def extract_from_pdf(pdf_path: str | Path) -> DocumentRecord:
    pdf_path = Path(pdf_path)
    lines = get_receipt_text_from_pdf(pdf_path)
    return extract_from_text_lines(lines, source_path=str(pdf_path), file_name=pdf_path.name)
