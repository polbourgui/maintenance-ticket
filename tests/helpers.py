from __future__ import annotations

import struct
import zlib

PASSWORD = "Str0ng-Passw0rd!"


def make_jpeg(*, with_exif: bool = True) -> bytes:
    def segment(marker: int, payload: bytes) -> bytes:
        return bytes([0xFF, marker]) + struct.pack(">H", len(payload) + 2) + payload

    parts = [b"\xff\xd8", segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")]
    if with_exif:
        parts.append(segment(0xE1, b"Exif\x00\x00GPS:48.8566,2.3522;Owner:Jean Dupont"))
        parts.append(segment(0xFE, b"comment with personal data"))
    parts.append(segment(0xDB, b"\x00" + bytes(64)))
    parts.append(segment(0xDA, b"\x01\x01\x00\x00\x3f\x00"))
    parts.append(b"\x12\x34\x56\x78" * 8 + b"\xff\xd9")
    return b"".join(parts)


def make_png(*, with_text: bool = True) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    if with_text:
        out += chunk(b"tEXt", b"Author\x00Jean Dupont")
    out += chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
    return out + chunk(b"IEND", b"")
