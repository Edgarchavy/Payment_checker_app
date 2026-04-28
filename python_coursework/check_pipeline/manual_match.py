from __future__ import annotations

from dataclasses import dataclass
import re

from .models import DocumentRecord


@dataclass
class ManualExpectation:
    expected_amount: str
    expected_currency: str
    expected_recipient_name: str
    expected_receipt_type: str
    expected_payer_name: str
    expected_reference_code: str


@dataclass
class ManualCheckResult:
    status: str
    score: str
    reasons: list[str]


def _normalized(value: str) -> str:
    return "".join(ch for ch in value.upper() if ch.isalnum())


def _same_text(left: str, right: str) -> bool:
    if not left and not right:
        return True
    return _normalized(left) == _normalized(right)


def _contains_code(document: DocumentRecord, code: str) -> bool:
    if not code:
        return True
    key = _normalized(code)
    haystack = _normalized(" ".join([document.reference, document.rrn, document.mcc_code, document.full_text]))
    return key in haystack


def check_payment(document: DocumentRecord, expectation: ManualExpectation) -> ManualCheckResult:
    score = 0
    total = 5
    reasons: list[str] = []
    amount_ok = False
    recipient_ok = False

    if document.amount == expectation.expected_amount:
        score += 1
        amount_ok = True
    else:
        reasons.append("sum")

    if document.currency == expectation.expected_currency:
        score += 1
    else:
        reasons.append("currency")

    if _same_text(document.recipient_name, expectation.expected_recipient_name):
        score += 1
        recipient_ok = True
    else:
        reasons.append("recipient")

    if not expectation.expected_receipt_type or document.receipt_type == expectation.expected_receipt_type:
        score += 1
    else:
        reasons.append("type")

    if (_same_text(document.payer_name, expectation.expected_payer_name) or not expectation.expected_payer_name) and _contains_code(document, expectation.expected_reference_code):
        score += 1
    else:
        if expectation.expected_payer_name and not _same_text(document.payer_name, expectation.expected_payer_name):
            reasons.append("payer")
        elif expectation.expected_reference_code and not _contains_code(document, expectation.expected_reference_code):
            reasons.append("payment_code")

    if not amount_ok or not recipient_ok:
        status = "Не оплачено"
    elif score == total:
        status = "Оплачено"
    elif score >= 3:
        status = "Частично оплачено"
    else:
        status = "Не оплачено"

    return ManualCheckResult(status=status, score=f"{score}/{total}", reasons=reasons)
