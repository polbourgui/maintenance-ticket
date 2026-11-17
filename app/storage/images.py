"""Image validation by magic bytes and metadata stripping (GDPR: EXIF may contain GPS data,
device serial numbers, author names...). Pure-Python, no native decoder attack surface."""

from __future__ import annotations

import struct
from dataclasses import dataclass

_JPEG_SOI = b"\xff\xd8"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# JPEG APPn segments carrying metadata: APP1 (EXIF/XMP), APP2..APP15 except APP14 (Adobe colour).
_JPEG_STRIP_MARKERS = frozenset(range(0xE1, 0xF0)) - {0xEE} | {0xFE}  # + COM
_PNG_STRIP_CHUNKS = frozenset({b"eXIf", b"tEXt", b"zTXt", b"iTXt", b"tIME"})


class ImageValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SanitizedImage:
    data: bytes
    content_type: str
    extension: str


def sanitize_image(data: bytes) -> SanitizedImage:
    if data.startswith(_JPEG_SOI):
        return SanitizedImage(_strip_jpeg(data), "image/jpeg", "jpg")
    if data.startswith(_PNG_SIGNATURE):
        return SanitizedImage(_strip_png(data), "image/png", "png")
    raise ImageValidationError("Unsupported file type: only JPEG and PNG images are accepted")


def _strip_jpeg(data: bytes) -> bytes:
    out = bytearray(_JPEG_SOI)
    pos = 2
    try:
        while pos < len(data):
            if data[pos] != 0xFF:
                raise ImageValidationError("Corrupted JPEG")
            marker = data[pos + 1]
            if marker == 0xD9:  # EOI
                out += data[pos : pos + 2]
                return bytes(out)
            if marker == 0xDA:  # SOS: the rest is entropy-coded image data
                out += data[pos:]
                return bytes(out)
            if 0xD0 <= marker <= 0xD7 or marker == 0x01:  # standalone markers
                out += data[pos : pos + 2]
                pos += 2
                continue
            (length,) = struct.unpack(">H", data[pos + 2 : pos + 4])
            if length < 2:
                raise ImageValidationError("Corrupted JPEG")
            segment_end = pos + 2 + length
            if segment_end > len(data):
                raise ImageValidationError("Truncated JPEG")
            if marker not in _JPEG_STRIP_MARKERS:
                out += data[pos:segment_end]
            pos = segment_end
    except (IndexError, struct.error) as exc:
        raise ImageValidationError("Corrupted JPEG") from exc
    raise ImageValidationError("Truncated JPEG")


def _strip_png(data: bytes) -> bytes:
    out = bytearray(_PNG_SIGNATURE)
    pos = len(_PNG_SIGNATURE)
    seen_ihdr = False
    while pos + 12 <= len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        chunk_type = data[pos + 4 : pos + 8]
        chunk_end = pos + 12 + length
        if chunk_end > len(data):
            raise ImageValidationError("Truncated PNG")
        if pos == len(_PNG_SIGNATURE):
            seen_ihdr = chunk_type == b"IHDR"
        if chunk_type not in _PNG_STRIP_CHUNKS:
            out += data[pos:chunk_end]
        pos = chunk_end
        if chunk_type == b"IEND":
            if not seen_ihdr:
                break
            return bytes(out)
    raise ImageValidationError("Invalid PNG")
