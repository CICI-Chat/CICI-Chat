from dataclasses import dataclass
from datetime import datetime, UTC
from hashlib import sha256
from json import dumps
from pathlib import Path

from PIL import Image as PillowImage
from sqlalchemy.orm import Session

from app.models import Annotation, Image
from app.services.annotation import create_mock_annotation
from app.services.scanner import find_image_files


@dataclass(frozen=True)
class IndexResult:
    added: int
    skipped: int
    errors: int


def calculate_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def index_folders(folders: list[Path], db: Session) -> IndexResult:
    added = 0
    skipped = 0
    errors = 0

    for path in find_image_files(folders):
        try:
            file_hash = calculate_sha256(path)
            exists = db.query(Image).filter(Image.file_hash == file_hash).first()
            if exists:
                skipped += 1
                continue

            stat = path.stat()
            with PillowImage.open(path) as image_file:
                width, height = image_file.size
                image_format = image_file.format or path.suffix.lstrip(".").upper()

            image = Image(
                file_path=str(path.resolve()),
                file_hash=file_hash,
                file_size=stat.st_size,
                width=width,
                height=height,
                format=image_format,
                created_at=datetime.fromtimestamp(stat.st_ctime, UTC),
                modified_at=datetime.fromtimestamp(stat.st_mtime, UTC),
                indexed_at=datetime.now(UTC),
            )
            db.add(image)
            db.flush()

            mock = create_mock_annotation()
            db.add(
                Annotation(
                    image_id=image.id,
                    caption=mock.caption,
                    tags=dumps(mock.tags, ensure_ascii=False),
                    objects=dumps(mock.objects, ensure_ascii=False),
                    model_used=mock.model_used,
                    created_at=datetime.now(UTC),
                )
            )
            db.commit()
            added += 1
        except Exception:
            db.rollback()
            errors += 1

    return IndexResult(added=added, skipped=skipped, errors=errors)
