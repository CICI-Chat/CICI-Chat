from pathlib import Path
from unittest.mock import MagicMock

from app.models import Annotation, Image
from app.services.indexer import get_file_created_at, index_folders


def test_index_folders_creates_image_and_annotation(db_session, sample_image):
    result = index_folders([sample_image.parent], db_session)

    assert result.added == 1
    assert result.skipped == 0
    assert result.errors == 0

    image = db_session.query(Image).one()
    annotation = db_session.query(Annotation).one()

    assert image.file_path == str(sample_image.resolve())
    assert image.file_size > 0
    assert image.width == 32
    assert image.height == 24
    assert image.format == "PNG"
    assert annotation.image_id == image.id
    assert annotation.caption == "待分析的本地图片"
    assert annotation.tags == '["本地图片", "待分析"]'


def test_index_folders_skips_duplicate_hash(db_session, sample_image):
    first = index_folders([sample_image.parent], db_session)
    second = index_folders([sample_image.parent], db_session)

    assert first.added == 1
    assert second.added == 0
    assert second.skipped == 1
    assert db_session.query(Image).count() == 1


def test_index_folders_handles_corrupt_image(db_session, tmp_path: Path):
    corrupt_path = tmp_path / "corrupt.png"
    corrupt_path.write_bytes(b"not a valid image")

    result = index_folders([tmp_path], db_session)

    assert result.added == 0
    assert result.skipped == 0
    assert result.errors == 1
    assert db_session.query(Image).count() == 0


def test_get_file_created_at_falls_back_to_mtime():
    mock_stat = MagicMock()
    del mock_stat.st_birthtime  # Simulate platform without st_birthtime
    mock_stat.st_mtime = 1700000000.0

    result = get_file_created_at(mock_stat)

    assert result.timestamp() == 1700000000.0
    assert result.tzinfo is not None  # Timezone-aware
