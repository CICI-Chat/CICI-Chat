from pathlib import Path

from app.services.scanner import find_image_files


def test_find_image_files_returns_supported_images(tmp_path: Path):
    image = tmp_path / "cat.JPG"
    nested = tmp_path / "nested"
    nested.mkdir()
    nested_image = nested / "dog.png"
    ignored = tmp_path / "notes.txt"
    image.write_bytes(b"fake")
    nested_image.write_bytes(b"fake")
    ignored.write_text("not image")

    result = find_image_files([tmp_path])

    assert result == [image, nested_image]


def test_find_image_files_skips_missing_folder(tmp_path: Path):
    assert find_image_files([tmp_path / "missing"]) == []
