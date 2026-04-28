from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image, ImageFilter, ImageOps


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


def preprocess_receipt_image(image_path: str | Path) -> Path:
    image_path = Path(image_path)
    image = Image.open(image_path).convert("RGB")

    bbox = _find_document_bbox(image)
    cropped = image.crop(bbox)

    target_width = max(cropped.width * 3, 1800)
    scale = target_width / cropped.width
    target_height = int(cropped.height * scale)
    resized = cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)

    grayscale = ImageOps.grayscale(resized)
    contrasted = ImageOps.autocontrast(grayscale)
    sharpened = contrasted.filter(ImageFilter.SHARPEN).filter(ImageFilter.SHARPEN)

    threshold = 185
    binary = sharpened.point(lambda value: 255 if value > threshold else 0, mode="1").convert("L")

    with NamedTemporaryFile(delete=False, suffix=".png") as tmp:
        output_path = Path(tmp.name)
    binary.save(output_path)
    return output_path
