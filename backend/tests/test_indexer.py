from app.models import Annotation, Image
from app.services.indexer import index_folders


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
