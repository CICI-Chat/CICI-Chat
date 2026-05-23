from pathlib import Path

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def find_image_files(folders: list[Path]) -> list[Path]:
    seen_images: set[Path] = set()
    seen_folders: set[Path] = set()
    for folder in folders:
        resolved = folder.resolve()
        if resolved in seen_folders:
            continue
        if not resolved.exists() or not resolved.is_dir():
            continue
        seen_folders.add(resolved)
        try:
            for path in resolved.rglob("*"):
                try:
                    if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                        seen_images.add(path.resolve())
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            continue
    return sorted(seen_images)
