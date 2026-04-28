from __future__ import annotations

from pathlib import Path
import re
import zlib


def _find_next_token(haystack: bytes, needle: bytes, start: int) -> int:
    limit = len(haystack) - len(needle) + 1
    for index in range(start, max(start, limit)):
        if haystack[index : index + len(needle)] == needle:
            return index
    return -1


def get_pdf_streams(path: str | Path) -> list[str | None]:
    data = Path(path).read_bytes()
    stream_token = b"stream"
    end_token = b"endstream"
    position = 0
    streams: list[str | None] = []

    while True:
        start = _find_next_token(data, stream_token, position)
        if start < 0:
            break
        stream_start = start + len(stream_token)
        if data[stream_start : stream_start + 2] == b"\r\n":
            stream_start += 2
        elif data[stream_start : stream_start + 1] == b"\n":
            stream_start += 1

        end = _find_next_token(data, end_token, stream_start)
        if end < 0:
            break

        chunk = data[stream_start:end]
        try:
            decoded = zlib.decompress(chunk).decode("latin-1")
            streams.append(decoded)
        except Exception:
            streams.append(None)
        position = end + len(end_token)

    return streams


def _build_cmap(stream_text: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if not stream_text:
        return result
    pattern = re.compile(r"^<([0-9A-Fa-f]{4})><([0-9A-Fa-f]{4})><([0-9A-Fa-f]{4})>$")
    for line in stream_text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        start_code = int(match.group(1), 16)
        end_code = int(match.group(2), 16)
        start_unicode = int(match.group(3), 16)
        for offset in range(end_code - start_code + 1):
            result[f"{start_code + offset:04X}"] = chr(start_unicode + offset)
    return result


def _decode_hex_text(hex_text: str, cmap: dict[str, str]) -> str:
    chars: list[str] = []
    for index in range(0, len(hex_text), 4):
        code = hex_text[index : index + 4].upper()
        if code in cmap:
            chars.append(cmap[code])
    return "".join(chars)


def _decode_literal_text(text: str) -> str:
    return text.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")


def get_receipt_text_from_pdf(path: str | Path) -> list[str]:
    streams = get_pdf_streams(path)
    cmaps = [_build_cmap(stream) for stream in streams if stream and "begincmap" in stream]
    cmaps = [item for item in cmaps if item]
    if len(cmaps) < 2:
        raise RuntimeError(f"Unable to build char maps for {path}")

    cmaps.sort(key=len)
    font3_map = cmaps[0]
    font1_map = cmaps[-1]
    content = streams[1] or ""
    font_name = ""
    parts: list[str] = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        font_match = re.search(r"/(F[123])\s+[0-9.]+\s+Tf", line)
        if font_match:
            font_name = font_match.group(1)
            continue

        hex_match = re.search(r"<([0-9A-Fa-f]+)>Tj", line)
        if hex_match:
            hex_text = hex_match.group(1)
            if font_name == "F1":
                decoded = _decode_hex_text(hex_text, font1_map)
            elif font_name == "F3":
                decoded = _decode_hex_text(hex_text, font3_map)
            else:
                decoded = hex_text
            if decoded:
                parts.append(decoded)
            continue

        literal_match = re.search(r"\((.*)\)Tj", line)
        if literal_match:
            decoded = _decode_literal_text(literal_match.group(1))
            if decoded != " ":
                parts.append(decoded)

    return parts
