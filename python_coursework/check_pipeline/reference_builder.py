from __future__ import annotations

from .models import DocumentRecord, ReferenceRecord


SCENARIO_OVERRIDES = {
    "513810530ea5ff33e67aadea5e34ee21.pdf": {
        "expected_amount": "350",
        "expected_status": "mismatch_expected",
        "scenario_note": "Intentional amount mismatch for demo",
    },
    "5fd3811eaeeb69761f65f91de555abf8.pdf": {
        "expected_recipient_name": "Predannoe Serdce Foundation",
        "expected_status": "partial_expected",
        "scenario_note": "Intentional recipient mismatch for demo",
    },
    "739c7e5b7d308a7682b84fddb0995703.pdf": {
        "expected_datetime": "23.04.2026 12:51:00",
        "expected_status": "partial_expected",
        "scenario_note": "Intentional date mismatch for demo",
    },
    "97eb0be6421e1a013c84b0f3dcf5ca6c.pdf": {
        "expected_currency": "BYN",
        "expected_status": "mismatch_expected",
        "scenario_note": "Intentional currency mismatch for demo",
    },
}


def build_reference(records: list[DocumentRecord]) -> list[ReferenceRecord]:
    result: list[ReferenceRecord] = []
    for record in records:
        payload = {
            "file_name": record.file_name,
            "expected_datetime": record.primary_datetime,
            "expected_amount": record.amount,
            "expected_currency": record.currency,
            "expected_recipient_name": record.recipient_name,
            "expected_receipt_type": record.receipt_type,
            "expected_status": "matched_expected",
            "scenario_note": "Exact reference generated from extracted check",
        }
        overrides = SCENARIO_OVERRIDES.get(record.file_name, {})
        payload.update(overrides)
        result.append(ReferenceRecord(**payload))
    return result
