from dataclasses import dataclass, asdict


@dataclass
class DocumentRecord:
    file_name: str
    source_path: str
    receipt_type: str
    primary_datetime: str
    amount: str
    currency: str
    recipient_name: str
    payer_name: str
    masked_card: str
    mcc_code: str
    iban_first: str
    iban_second: str
    rrn: str
    authorization_code: str
    reference: str
    full_text: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReferenceRecord:
    file_name: str
    expected_datetime: str
    expected_amount: str
    expected_currency: str
    expected_recipient_name: str
    expected_receipt_type: str
    expected_status: str
    scenario_note: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MatchResult:
    file_name: str
    actual_amount: str
    expected_amount: str
    actual_currency: str
    expected_currency: str
    actual_datetime: str
    expected_datetime: str
    actual_recipient_name: str
    expected_recipient_name: str
    actual_receipt_type: str
    expected_receipt_type: str
    score: str
    status: str
    mismatch_reasons: str
    source_path: str

    def to_dict(self) -> dict:
        return asdict(self)
