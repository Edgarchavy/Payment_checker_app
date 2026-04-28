from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import contextlib

from .image_preprocess import preprocess_receipt_image


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


def extract_text_with_tesseract(image_path: str | Path, lang: str = "rus+eng") -> str:
    image_path = Path(image_path)
    tesseract_cmd = find_tesseract_executable()
    processed_image = preprocess_receipt_image(image_path)
    try:
        command = [
            tesseract_cmd,
            str(processed_image),
            "stdout",
            "-l",
            lang,
            "--psm",
            "11",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or "Unknown Tesseract error"
            raise RuntimeError(stderr)
        return completed.stdout
    finally:
        with contextlib.suppress(OSError):
            processed_image.unlink()
