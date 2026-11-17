from __future__ import annotations

from pathlib import Path

import pytest

from app.storage import ImageValidationError, LocalFileStorage, sanitize_image
from tests.helpers import make_jpeg, make_png


def test_jpeg_metadata_stripped() -> None:
    original = make_jpeg()
    image = sanitize_image(original)
    assert image.content_type == "image/jpeg"
    assert b"Exif" not in image.data
    assert b"personal data" not in image.data
    assert b"JFIF" in image.data  # non-metadata segments preserved
    assert image.data.endswith(b"\xff\xd9")
    assert sanitize_image(make_jpeg(with_exif=False)).data == make_jpeg(with_exif=False)


def test_png_text_chunks_stripped() -> None:
    image = sanitize_image(make_png())
    assert image.content_type == "image/png"
    assert b"tEXt" not in image.data
    assert image.data == make_png(with_text=False)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"GIF89a",
        b"<?php",
        b"\xff\xd8\xff\xe1\x00",
        b"\xff\xd8\x00\x00",
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR",
        b"\x89PNG\r\n\x1a\n",
    ],
)
def test_invalid_images_rejected(payload: bytes) -> None:
    with pytest.raises(ImageValidationError):
        sanitize_image(payload)


def test_local_storage_roundtrip_and_traversal(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    key = "0" * 32 + ".jpg"
    storage.save(key, b"data")
    assert storage.read(key) == b"data"
    with pytest.raises(FileExistsError):
        storage.save(key, b"overwrite")
    storage.delete(key)
    with pytest.raises(FileNotFoundError):
        storage.read(key)
    for bad in ["../../etc/passwd", "a" * 32 + ".exe", "/abs.jpg", "A" * 32 + ".jpg"]:
        with pytest.raises(ValueError, match="Invalid storage key"):
            storage.save(bad, b"x")
