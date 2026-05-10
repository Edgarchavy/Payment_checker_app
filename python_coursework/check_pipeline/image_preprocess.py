from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def _find_document_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()

    min_x, min_y = width, height
    max_x, max_y = 0, 0

    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if r > 210 and g > 210 and b > 210:
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y

    if min_x >= max_x or min_y >= max_y:
        return (0, 0, width, height)

    pad = 10
    return (
        max(0, min_x - pad),
        max(0, min_y - pad),
        min(width, max_x + pad),
        min(height, max_y + pad),
    )


def _save_tmp(image: Image.Image, suffix: str = ".png") -> Path:
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        output_path = Path(tmp.name)
    image.save(output_path)
    return output_path


def _resize_for_ocr(image: Image.Image, min_width: int = 1800, scale_factor: int = 3) -> Image.Image:
    target_width = max(image.width * scale_factor, min_width)
    scale = target_width / image.width
    target_height = int(image.height * scale)
    return image.resize((target_width, target_height), Image.Resampling.LANCZOS)


def _basic_cleanup(image: Image.Image) -> Image.Image:
    grayscale = ImageOps.grayscale(image)
    contrasted = ImageOps.autocontrast(grayscale)
    contrasted = ImageEnhance.Contrast(contrasted).enhance(1.8)
    sharpened = contrasted.filter(ImageFilter.SHARPEN).filter(ImageFilter.SHARPEN)
    return sharpened


def _binary(image: Image.Image, threshold: int) -> Image.Image:
    return image.point(lambda value: 255 if value > threshold else 0, mode="1").convert("L")


def _denoise(image: Image.Image) -> Image.Image:
    return image.filter(ImageFilter.MedianFilter(size=3))


def preprocess_receipt_image_variants(image_path: str | Path) -> list[tuple[str, Path]]:
    """Build several OCR-ready image variants and let OCR choose the best text.

    Different photos fail in different ways: some need strong binarization, some
    lose thin letters after thresholding. Running a small ensemble of variants is
    slower, but noticeably more robust for coursework demo images.
    """
    image_path = Path(image_path)
    image = Image.open(image_path).convert("RGB")

    bbox = _find_document_bbox(image)
    cropped = image.crop(bbox)
    resized = _resize_for_ocr(cropped)
    cleaned = _basic_cleanup(resized)
    denoised = _denoise(cleaned)

    variants = [
        ("gray_autocontrast_sharpen", cleaned),
        ("denoise_soft_binary", _binary(denoised, 165)),
        ("balanced_binary", _binary(cleaned, 185)),
        ("strong_binary", _binary(cleaned, 205)),
        ("inverted_safe", ImageOps.invert(_binary(cleaned, 185)).convert("L")),
    ]

    return [(name, _save_tmp(variant)) for name, variant in variants]


def preprocess_receipt_image(image_path: str | Path) -> Path:
    return preprocess_receipt_image_variants(image_path)[2][1]
