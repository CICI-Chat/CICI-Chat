from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PillowImage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.services.indexer import index_folders


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.config import Settings
    from app.database import get_db
    from app.main import create_app

    test_settings = Settings(watch_folders=str(tmp_path), db_path=tmp_path / "api.db")
    monkeypatch.setattr("app.api.reindex.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.settings.get_settings", lambda: test_settings)
    app = create_app(run_startup_indexing=False)

    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    image_path = tmp_path / "sample.png"
    image = PillowImage.new("RGB", (32, 24), color="red")
    image.save(image_path)

    with SessionLocal() as session:
        result = index_folders([tmp_path], session)
        assert result.added == 1

    def override_get_db():
        db: Session = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_get_images_returns_indexed_image_with_mock_annotation(api_client: TestClient):
    response = api_client.get("/api/images")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["page"] == 1
    assert payload["size"] == 50
    assert payload["items"][0]["caption"] == "待分析的本地图片"
    assert payload["items"][0]["tags"] == ["本地图片", "待分析"]
    assert payload["items"][0]["image_url"].startswith("/api/images/")


def test_get_stats_counts_images_formats_and_tags(api_client: TestClient):
    response = api_client.get("/api/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_images"] == 1
    assert payload["formats"] == {"PNG": 1}
    assert payload["tags"] == {"本地图片": 1, "待分析": 1}


def test_get_settings_returns_mock_provider(api_client: TestClient):
    response = api_client.get("/api/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "mock"
    assert isinstance(payload["watch_folders"], list)
    assert isinstance(payload["db_path"], str)


def test_get_image_detail_returns_objects_and_model_used(api_client: TestClient):
    images = api_client.get("/api/images").json()["items"]

    response = api_client.get(f"/api/images/{images[0]['id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["objects"] == []
    assert payload["model_used"] == "mock"


def test_get_missing_image_returns_404(api_client: TestClient):
    response = api_client.get("/api/images/missing")

    assert response.status_code == 404


def test_get_image_file_returns_stored_file(api_client: TestClient):
    image_id = api_client.get("/api/images").json()["items"][0]["id"]

    response = api_client.get(f"/api/images/{image_id}/file")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_post_reindex_returns_index_result(api_client: TestClient):
    response = api_client.post("/api/reindex")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"added", "skipped", "errors"}
