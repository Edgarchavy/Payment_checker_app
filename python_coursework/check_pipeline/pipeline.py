from __future__ import annotations

from pathlib import Path
import shutil

from .field_extractor import extract_from_pdf
from .io_utils import ensure_dir, write_csv, write_json, write_xlsx_from_rows
from .matcher import match_all
from .models import DocumentRecord
from .reference_builder import build_reference


def extract_documents(source_dir: str | Path) -> list[DocumentRecord]:
    source_dir = Path(source_dir)
    records = []
    for pdf_path in sorted(source_dir.glob("*.pdf")):
        records.append(extract_from_pdf(pdf_path))
    return records


def run_all(workspace_root: str | Path) -> dict[str, Path]:
    workspace_root = Path(workspace_root)
    source_dir = workspace_root / "Cheki"
    output_root = workspace_root / "project_output_py"
    extracted_dir = ensure_dir(output_root / "01_extracted")
    reference_dir = ensure_dir(output_root / "02_reference")
    results_dir = ensure_dir(output_root / "03_results")
    copied_pdf_dir = ensure_dir(output_root / "00_source_pdf")

    for pdf_path in sorted(source_dir.glob("*.pdf")):
        shutil.copy2(pdf_path, copied_pdf_dir / pdf_path.name)

    extracted = extract_documents(source_dir)
    write_csv(extracted_dir / "extracted_checks.csv", extracted)
    write_json(extracted_dir / "extracted_checks.json", extracted)
    write_xlsx_from_rows(
        extracted_dir / "extracted_checks.xlsx",
        extracted,
        widths={1: 34, 2: 24, 3: 22, 4: 10, 5: 10, 6: 42, 7: 28, 8: 12, 9: 12, 10: 24, 11: 24, 12: 18, 13: 18, 14: 18, 15: 18, 16: 100},
        title="Extracted checks",
    )

    reference = build_reference(extracted)
    write_csv(reference_dir / "reference_payments.csv", reference)
    write_json(reference_dir / "reference_payments.json", reference)
    write_xlsx_from_rows(
        reference_dir / "reference_payments.xlsx",
        reference,
        widths={1: 34, 2: 22, 3: 12, 4: 10, 5: 42, 6: 24, 7: 18, 8: 38},
        title="Reference payments",
    )

    results = match_all(extracted, reference)
    write_csv(results_dir / "matching_results.csv", results)
    write_json(results_dir / "matching_results.json", results)
    write_xlsx_from_rows(
        results_dir / "matching_results.xlsx",
        results,
        widths={1: 34, 2: 12, 3: 12, 4: 10, 5: 10, 6: 22, 7: 22, 8: 42, 9: 42, 10: 24, 11: 24, 12: 10, 13: 18, 14: 28, 15: 50},
        title="Matching results",
    )

    return {
        "copied_pdf_dir": copied_pdf_dir,
        "extracted_dir": extracted_dir,
        "reference_dir": reference_dir,
        "results_dir": results_dir,
    }
