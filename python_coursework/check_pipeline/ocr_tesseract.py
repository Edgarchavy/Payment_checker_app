from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import contextlib
import re

from .image_preprocess import preprocess_receipt_image_variants


DEFAULT_TESSERACT_PATHS = [
    str(Path(__file__).resolve().parents[2] / "Tesseract-OCR" / "tesseract.exe"),
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def find_tesseract_executable() -> str:
    env_path = os.environ.get("TESSERACT_CMD")
    if env_path and Path(env_path).exists():
        return env_path

    discovered = shutil.which("tesseract")
    if discovered:
        return discovered

    for candidate in DEFAULT_TESSERACT_PATHS:
        if Path(candidate).exists():
            return candidate

    raise RuntimeError(
        "Tesseract not found. Install Tesseract OCR or set TESSERACT_CMD to the full path of tesseract.exe"
    )


def _run_tesseract(tesseract_cmd: str, image_path: Path, lang: str, psm: str) -> str:
    command = [
        tesseract_cmd,
        str(image_path),
        "stdout",
        "-l",
        lang,
        "--oem",
        "1",
        "--psm",
        psm,
        "-c",
        "preserve_interword_spaces=1",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or "Unknown Tesseract error"
        raise RuntimeError(stderr)
    return completed.stdout


def _ocr_quality_score(text: str) -> int:
    normalized = text.upper()
    score = 0
    score += min(len(re.findall(r"[А-ЯA-Z]{3,}", normalized)), 80)
    score += 25 * len(re.findall(r"\b\d+[,.]?\d*\s*(?:BYN|USD|EUR|RUB)\b", normalized))
    score += 20 * len(re.findall(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", normalized))
    score += 15 * len(re.findall(r"\bRRN\b|\bMCC\b|ЕРИП|ERIP|СУММА|ПЛАТЕЛЬЩИК|ПОЛУЧАТЕЛЬ", normalized))
    score -= 2 * normalized.count("�")
    return score


def extract_text_with_tesseract(image_path: str | Path, lang: str = "rus+eng") -> str:
    image_path = Path(image_path)
    tesseract_cmd = find_tesseract_executable()
    processed_images = preprocess_receipt_image_variants(image_path)
    psm_modes = ["6", "4", "11"]

    best_text = ""
    best_score = -1
    last_error: Exception | None = None

    try:
        for _variant_name, processed_image in processed_images:
            for psm in psm_modes:
                try:
                    text = _run_tesseract(tesseract_cmd, processed_image, lang, psm)
                except Exception as exc:  # keep trying other variants
                    last_error = exc
                    continue
                score = _ocr_quality_score(text)
                if score > best_score:
                    best_score = score
                    best_text = text

        if best_text.strip():
            return best_text
        if last_error:
            raise last_error
        return ""
    finally:
        for _variant_name, processed_image in processed_images:
            with contextlib.suppress(OSError):
                processed_image.unlink()
