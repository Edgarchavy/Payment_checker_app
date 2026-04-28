from __future__ import annotations

import argparse
from pathlib import Path

from check_pipeline.field_extractor import extract_from_pdf
from check_pipeline.pipeline import extract_documents, run_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Coursework pipeline for receipt extraction and matching")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_all_parser = subparsers.add_parser("run-all", help="Run the full coursework pipeline")
    run_all_parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))

    extract_parser = subparsers.add_parser("extract-one", help="Extract one PDF receipt")
    extract_parser.add_argument("pdf_path")

    extract_all_parser = subparsers.add_parser("extract-all", help="Extract all PDFs from Cheki")
    extract_all_parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))

    args = parser.parse_args()

    if args.command == "run-all":
        outputs = run_all(args.root)
        for name, path in outputs.items():
            print(f"{name}: {path}")
        return

    if args.command == "extract-one":
        record = extract_from_pdf(args.pdf_path)
        for key, value in record.to_dict().items():
            print(f"{key}: {value}")
        return

    if args.command == "extract-all":
        records = extract_documents(Path(args.root) / "Cheki")
        print(f"records: {len(records)}")
        for item in records:
            print(item.file_name)


if __name__ == "__main__":
    main()
