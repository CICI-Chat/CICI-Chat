from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Annotation, Image


def test_database_models_create_expected_tables(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")

    Base.metadata.create_all(bind=engine)

    tables = set(inspect(engine).get_table_names())
    assert tables == {"images", "annotations"}
    assert Image.__tablename__ == "images"
    assert Annotation.__tablename__ == "annotations"


def test_insert_image_and_annotation_relation_and_default_times(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        image = Image(
            file_path="/tmp/test.jpg",
            file_hash="abc123",
            file_size=1024,
            width=800,
            height=600,
            format="JPEG",
        )
        session.add(image)
        session.flush()

        annotation = Annotation(
            image_id=image.id,
            caption="A test image",
            tags='["nature", "outdoor"]',
            objects='[{"label": "tree", "confidence": 0.9}]',
            model_used="test-model",
        )
        session.add(annotation)
        session.commit()

        # Refresh to ensure values are loaded from DB
        session.refresh(image)
        session.refresh(annotation)

        # Default timestamps are populated
        assert image.created_at is not None
        assert image.modified_at is not None
        assert image.indexed_at is not None
        assert annotation.created_at is not None

        # Bidirectional relationship works
        assert image.annotation is annotation
        assert annotation.image is image


def test_duplicate_file_hash_raises_integrity_error(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        image1 = Image(
            file_path="/tmp/one.jpg",
            file_hash="same-hash",
            file_size=100,
            width=10,
            height=10,
            format="PNG",
        )
        session.add(image1)
        session.commit()

        image2 = Image(
            file_path="/tmp/two.jpg",
            file_hash="same-hash",
            file_size=200,
            width=20,
            height=20,
            format="PNG",
        )
        session.add(image2)

        try:
            session.commit()
            raise AssertionError("Expected IntegrityError was not raised")
        except IntegrityError:
            session.rollback()


def test_delete_image_cascades_to_annotation(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        image = Image(
            file_path="/tmp/cascade.jpg",
            file_hash="cascade-hash",
            file_size=512,
            width=32,
            height=32,
            format="GIF",
        )
        session.add(image)
        session.flush()

        annotation = Annotation(
            image_id=image.id,
            caption="Cascade test",
            tags="[]",
            objects="[]",
            model_used="test-model",
        )
        session.add(annotation)
        session.commit()

        image_id = image.id

        # Confirm annotation exists
        assert session.get(Annotation, image_id) is not None

        # Delete the image
        session.delete(image)
        session.commit()

        # Annotation should be gone via cascade/delete-orphan
        assert session.get(Annotation, image_id) is None
