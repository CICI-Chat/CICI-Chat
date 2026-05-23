from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.database import Base
from app.models import Annotation, Image


def test_database_models_create_expected_tables(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")

    Base.metadata.create_all(bind=engine)

    tables = set(inspect(engine).get_table_names())
    assert tables == {"images", "annotations"}
    assert Image.__tablename__ == "images"
    assert Annotation.__tablename__ == "annotations"
