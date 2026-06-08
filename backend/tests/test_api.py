import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image as PillowImage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import Annotation, Image, RecognitionBatch, RecognitionBatchItem
from app.services.indexer import index_folders


@contextmanager
def make_api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.config import Settings, get_settings
    from app.database import get_db
    from app.main import create_app

    tmp_path.mkdir(parents=True, exist_ok=True)
    test_settings = Settings(watch_folders=str(tmp_path), db_path=tmp_path / "api.db")
    monkeypatch.setattr("app.api.images.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.reindex.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.settings.get_settings", lambda: test_settings)
    app = create_app(run_startup_indexing=False, run_batch_worker=False)

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
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def add_indexed_image(
    db: Session,
    tmp_path: Path,
    *,
    filename: str,
    size: tuple[int, int],
    color: str,
    caption: str,
    tags: list[str],
    file_size: int,
    format: str,
    modified_at: datetime,
    indexed_at: datetime,
) -> Image:
    image_path = tmp_path / filename
    image_path.parent.mkdir(parents=True, exist_ok=True)
    PillowImage.new("RGB", size, color=color).save(image_path)
    image = Image(
        file_path=str(image_path.resolve()),
        file_hash=f"hash-{filename}",
        file_size=file_size,
        width=size[0],
        height=size[1],
        format=format,
        created_at=modified_at,
        modified_at=modified_at,
        indexed_at=indexed_at,
    )
    db.add(image)
    db.flush()
    db.add(
        Annotation(
            image_id=image.id,
            caption=caption,
            tags=json.dumps(tags, ensure_ascii=False),
            objects="[]",
            model_used="mock",
        )
    )
    db.commit()
    db.refresh(image)
    return image


@contextmanager
def make_api_db_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.config import Settings, get_settings
    from app.database import get_db
    from app.main import create_app

    tmp_path.mkdir(parents=True, exist_ok=True)
    test_settings = Settings(watch_folders=str(tmp_path), db_path=tmp_path / "api-batch-history.db")
    monkeypatch.setattr("app.api.images.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.reindex.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.settings.get_settings", lambda: test_settings)
    app = create_app(run_startup_indexing=False, run_batch_worker=False)

    engine = create_engine(f"sqlite:///{tmp_path / 'api-batch-history.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db: Session = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        with TestClient(app) as client, SessionLocal() as session:
            yield client, session
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


@contextmanager
def make_gallery_query_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    include_color_search_images: bool = False,
    extra_travel_images: int = 0,
):
    from app.config import Settings, get_settings
    from app.database import get_db
    from app.main import create_app

    tmp_path.mkdir(parents=True, exist_ok=True)
    test_settings = Settings(watch_folders=str(tmp_path), db_path=tmp_path / "gallery-query.db")
    monkeypatch.setattr("app.api.images.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.reindex.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.settings.get_settings", lambda: test_settings)
    app = create_app(run_startup_indexing=False, run_batch_worker=False)

    engine = create_engine(f"sqlite:///{tmp_path / 'gallery-query.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    now = datetime(2026, 5, 29, 12, 0, tzinfo=UTC)
    with SessionLocal() as session:
        add_indexed_image(
            session,
            tmp_path,
            filename="mountain.png",
            size=(64, 32),
            color="red",
            caption="雪山日出",
            tags=["自然", "旅行"],
            file_size=300,
            format="PNG",
            modified_at=now - timedelta(days=2),
            indexed_at=now - timedelta(minutes=3),
        )
        add_indexed_image(
            session,
            tmp_path,
            filename="city.jpg",
            size=(32, 64),
            color="blue",
            caption="城市夜景",
            tags=["城市", "夜景"],
            file_size=100,
            format="JPEG",
            modified_at=now - timedelta(days=1),
            indexed_at=now - timedelta(minutes=2),
        )
        add_indexed_image(
            session,
            tmp_path,
            filename="family.png",
            size=(48, 48),
            color="green",
            caption="家庭相册",
            tags=["人物", "旅行"],
            file_size=200,
            format="PNG",
            modified_at=now,
            indexed_at=now - timedelta(minutes=1),
        )
        add_indexed_image(
            session,
            tmp_path,
            filename="travel/beach.png",
            size=(40, 30),
            color="yellow",
            caption="海边旅行",
            tags=["旅行"],
            file_size=500,
            format="PNG",
            modified_at=now + timedelta(minutes=11),
            indexed_at=now + timedelta(minutes=11),
        )
        add_indexed_image(
            session,
            tmp_path,
            filename="travel/mountain.png",
            size=(42, 30),
            color="blue",
            caption="山间旅行",
            tags=["旅行"],
            file_size=501,
            format="PNG",
            modified_at=now + timedelta(minutes=12),
            indexed_at=now + timedelta(minutes=12),
        )
        add_indexed_image(
            session,
            tmp_path,
            filename="family/portrait.png",
            size=(30, 42),
            color="green",
            caption="家庭照片",
            tags=["家庭"],
            file_size=502,
            format="PNG",
            modified_at=now + timedelta(minutes=13),
            indexed_at=now + timedelta(minutes=13),
        )
        for index in range(extra_travel_images):
            add_indexed_image(
                session,
                tmp_path,
                filename=f"travel/extra-{index}.png",
                size=(24, 24),
                color="yellow",
                caption=f"额外旅行 {index}",
                tags=["旅行"],
                file_size=600 + index,
                format="PNG",
                modified_at=now + timedelta(minutes=20 + index),
                indexed_at=now + timedelta(minutes=20 + index),
            )
        if include_color_search_images:
            add_indexed_image(
                session,
                tmp_path,
                filename="exact-yellow.png",
                size=(40, 40),
                color="yellow",
                caption="颜色样本一",
                tags=["黄色"],
                file_size=400,
                format="PNG",
                modified_at=now + timedelta(minutes=1),
                indexed_at=now + timedelta(minutes=1),
            )
            add_indexed_image(
                session,
                tmp_path,
                filename="deep-yellow.png",
                size=(40, 40),
                color="yellow",
                caption="颜色样本二",
                tags=["深黄色"],
                file_size=401,
                format="PNG",
                modified_at=now + timedelta(minutes=2),
                indexed_at=now + timedelta(minutes=2),
            )
            add_indexed_image(
                session,
                tmp_path,
                filename="light-yellow.png",
                size=(40, 40),
                color="yellow",
                caption="颜色样本三",
                tags=["浅黄色"],
                file_size=402,
                format="PNG",
                modified_at=now + timedelta(minutes=3),
                indexed_at=now + timedelta(minutes=3),
            )
            add_indexed_image(
                session,
                tmp_path,
                filename="sample-a.png",
                size=(40, 40),
                color="red",
                caption="颜色样本四",
                tags=["浅红色"],
                file_size=403,
                format="PNG",
                modified_at=now + timedelta(minutes=4),
                indexed_at=now + timedelta(minutes=4),
            )
            add_indexed_image(
                session,
                tmp_path,
                filename="sample-b.png",
                size=(40, 40),
                color="red",
                caption="颜色样本五",
                tags=["红色"],
                file_size=404,
                format="PNG",
                modified_at=now + timedelta(minutes=5),
                indexed_at=now + timedelta(minutes=5),
            )
            add_indexed_image(
                session,
                tmp_path,
                filename="sample-c.png",
                size=(40, 40),
                color="red",
                caption="颜色样本六",
                tags=["深红色"],
                file_size=405,
                format="PNG",
                modified_at=now + timedelta(minutes=6),
                indexed_at=now + timedelta(minutes=6),
            )
            add_indexed_image(
                session,
                tmp_path,
                filename="sample-d.png",
                size=(40, 40),
                color="blue",
                caption="颜色样本七",
                tags=["浅蓝色"],
                file_size=406,
                format="PNG",
                modified_at=now + timedelta(minutes=7),
                indexed_at=now + timedelta(minutes=7),
            )
            add_indexed_image(
                session,
                tmp_path,
                filename="sample-e.png",
                size=(40, 40),
                color="blue",
                caption="颜色样本八",
                tags=["蓝色"],
                file_size=407,
                format="PNG",
                modified_at=now + timedelta(minutes=8),
                indexed_at=now + timedelta(minutes=8),
            )
            add_indexed_image(
                session,
                tmp_path,
                filename="sample-f.png",
                size=(40, 40),
                color="blue",
                caption="颜色样本九",
                tags=["深蓝色"],
                file_size=408,
                format="PNG",
                modified_at=now + timedelta(minutes=9),
                indexed_at=now + timedelta(minutes=9),
            )
            add_indexed_image(
                session,
                tmp_path,
                filename="sample-g.png",
                size=(40, 40),
                color="black",
                caption="颜色样本十",
                tags=["%"],
                file_size=409,
                format="PNG",
                modified_at=now + timedelta(minutes=10),
                indexed_at=now + timedelta(minutes=10),
            )

    def override_get_db():
        db: Session = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_api_client(tmp_path, monkeypatch) as client:
        yield client


def test_get_images_returns_indexed_image_with_mock_annotation(api_client: TestClient):
    response = api_client.get("/api/images")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["page"] == 1
    assert payload["size"] == 50
    assert payload["items"][0]["caption"] == "待分析的本地图片"
    assert payload["items"][0]["tags"] == ["本地图片", "待分析"]
    assert payload["items"][0]["model_used"] == "mock"
    assert payload["items"][0]["image_url"].startswith("/api/images/")


def test_list_images_searches_caption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/images", params={"q": "夜景"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["caption"] for item in payload["items"]] == ["城市夜景"]


def test_list_images_searches_tags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/images", params={"q": "人物"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["caption"] for item in payload["items"]] == ["家庭相册"]


def test_list_images_searches_color_family_with_chinese_base_color(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    with make_gallery_query_client(tmp_path, monkeypatch, include_color_search_images=True) as client:
        response = client.get("/api/images", params={"q": "红色", "sort": "file_size", "order": "asc"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert [item["tags"] for item in payload["items"]] == [["浅红色"], ["红色"], ["深红色"]]


def test_list_images_searches_color_family_with_english_base_color(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    with make_gallery_query_client(tmp_path, monkeypatch, include_color_search_images=True) as client:
        response = client.get("/api/images", params={"q": "blue", "sort": "file_size", "order": "asc"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert [item["tags"] for item in payload["items"]] == [["浅蓝色"], ["蓝色"], ["深蓝色"]]


def test_list_images_searches_light_color_with_english_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch, include_color_search_images=True) as client:
        response = client.get("/api/images", params={"q": "light yellow"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["tags"] for item in payload["items"]] == [["浅黄色"]]


def test_list_images_escapes_tag_search_wildcards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch, include_color_search_images=True) as client:
        response = client.get("/api/images", params={"q": "%"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["tags"] for item in payload["items"]] == [["%"]]


def test_list_images_escapes_tag_filter_wildcards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch, include_color_search_images=True) as client:
        response = client.get("/api/images", params={"tag": "%"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["tags"] for item in payload["items"]] == [["%"]]


def test_list_images_searches_file_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/images", params={"q": "city"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["caption"] for item in payload["items"]] == ["城市夜景"]


def test_list_images_filters_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get(
            "/api/images",
            params={"folder": str((tmp_path / "travel").resolve()), "sort": "file_size", "order": "asc"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [item["caption"] for item in payload["items"]] == ["海边旅行", "山间旅行"]


def test_list_images_rejects_folder_outside_watch_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/images", params={"folder": str(tmp_path.parent.resolve())})

    assert response.status_code == 400
    assert response.json()["detail"] == "Folder must be inside a watch folder"


def test_get_image_folders_returns_indexed_subfolders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/images/folders")

    assert response.status_code == 200
    folders = response.json()
    folder_counts = {Path(folder["path"]).name: folder["image_count"] for folder in folders}
    assert folder_counts["travel"] == 2
    assert folder_counts["family"] == 1


def test_list_images_filters_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get(
            "/api/images",
            params={"format": "PNG", "sort": "file_size", "order": "asc"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 5
    assert [item["caption"] for item in payload["items"]] == ["家庭相册", "雪山日出", "海边旅行", "山间旅行", "家庭照片"]


def test_list_images_combines_tag_and_search(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/images", params={"tag": "旅行", "q": "家庭"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["caption"] for item in payload["items"]] == ["家庭相册"]


def test_list_images_sorts_by_width_desc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/images", params={"sort": "width", "order": "desc"})

    assert response.status_code == 200
    payload = response.json()
    assert [item["caption"] for item in payload["items"]] == ["雪山日出", "家庭相册", "山间旅行", "海边旅行", "城市夜景", "家庭照片"]


def test_list_images_rejects_unknown_sort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/images", params={"sort": "caption"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported sort field"


def test_list_images_rejects_unknown_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/images", params={"order": "sideways"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported sort order"


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


def test_post_recognize_image_returns_refreshed_detail(api_client: TestClient):
    image_id = api_client.get("/api/images").json()["items"][0]["id"]

    response = api_client.post(f"/api/images/{image_id}/recognize")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == image_id
    assert payload["caption"] == "待分析的本地图片"
    assert payload["tags"] == ["本地图片", "landscape", "红色"]
    assert payload["objects"] == []
    assert payload["model_used"] == "mock"


def test_list_images_searches_recognized_refined_color_tag(api_client: TestClient):
    image_id = api_client.get("/api/images").json()["items"][0]["id"]
    recognize_response = api_client.post(f"/api/images/{image_id}/recognize")
    assert recognize_response.status_code == 200

    response = api_client.get("/api/images", params={"q": "红色"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == image_id
    assert "红色" in payload["items"][0]["tags"]


def test_post_recognize_missing_image_returns_404(api_client: TestClient):
    response = api_client.post("/api/images/missing/recognize")

    assert response.status_code == 404
    assert response.json()["detail"] == "Image not found"


def test_get_recognition_batches_returns_history_newest_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    image_1 = Image(
        id="history-image-1",
        file_path="/tmp/history-image-1.png",
        file_hash="history-hash-1",
        file_size=100,
        width=32,
        height=24,
        format="PNG",
        created_at=now,
        modified_at=now,
        indexed_at=now,
    )
    image_2 = Image(
        id="history-image-2",
        file_path="/tmp/history-image-2.png",
        file_hash="history-hash-2",
        file_size=100,
        width=32,
        height=24,
        format="PNG",
        created_at=now,
        modified_at=now,
        indexed_at=now,
    )
    older = RecognitionBatch(
        id="api-batch-older",
        status="completed",
        total=1,
        created_at=datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
    )
    newer = RecognitionBatch(
        id="api-batch-newer",
        status="failed",
        total=1,
        created_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
    )
    older.items = [RecognitionBatchItem(image_id="history-image-1", status="completed")]
    newer.items = [RecognitionBatchItem(image_id="history-image-2", status="failed", error="boom")]

    with make_api_db_client(tmp_path, monkeypatch) as (client, db_session):
        db_session.add_all([image_1, image_2, older, newer])
        db_session.commit()

        response = client.get("/api/recognition/batches", params={"page": 1, "size": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["size"] == 1
    assert [item["batch_id"] for item in body["items"]] == ["api-batch-newer"]
    assert body["items"][0]["failed"] == 1
    assert body["items"][0]["created_at"].startswith("2026-06-07T12:00:00")


def test_get_recognition_batches_filters_by_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    image_1 = Image(id="status-image-1", file_path="/tmp/status-image-1.png", file_hash="status-hash-1", file_size=100, width=32, height=24, format="PNG", created_at=now, modified_at=now, indexed_at=now)
    image_2 = Image(id="status-image-2", file_path="/tmp/status-image-2.png", file_hash="status-hash-2", file_size=100, width=32, height=24, format="PNG", created_at=now, modified_at=now, indexed_at=now)
    completed = RecognitionBatch(id="api-batch-completed", status="completed", total=1, created_at=datetime(2026, 6, 5, 12, 0, tzinfo=UTC))
    failed = RecognitionBatch(id="api-batch-failed", status="failed", total=1, created_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC))
    completed.items = [RecognitionBatchItem(image_id="status-image-1", status="completed")]
    failed.items = [RecognitionBatchItem(image_id="status-image-2", status="failed")]

    with make_api_db_client(tmp_path, monkeypatch) as (client, db_session):
        db_session.add_all([image_1, image_2, completed, failed])
        db_session.commit()

        response = client.get("/api/recognition/batches", params={"page": 1, "size": 20, "status": "failed"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["batch_id"] for item in body["items"]] == ["api-batch-failed"]


def test_get_recognition_batches_rejects_unknown_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_api_db_client(tmp_path, monkeypatch) as (client, _db_session):
        response = client.get("/api/recognition/batches", params={"status": "unknown"})

    assert response.status_code == 422


def test_get_recognition_batch_items_filters_failed_and_returns_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    failed_image = Image(
        id="api-item-failed",
        file_path="/tmp/api-item-failed.png",
        file_hash="api-item-failed-hash",
        file_size=100,
        width=32,
        height=24,
        format="PNG",
        created_at=now,
        modified_at=now,
        indexed_at=now,
    )
    completed_image = Image(
        id="api-item-completed",
        file_path="/tmp/api-item-completed.png",
        file_hash="api-item-completed-hash",
        file_size=100,
        width=32,
        height=24,
        format="PNG",
        created_at=now,
        modified_at=now,
        indexed_at=now,
    )
    batch = RecognitionBatch(id="api-batch-items", status="failed", total=2)
    failed_item = RecognitionBatchItem(image_id="api-item-failed", status="failed", error="missing file")
    batch.items = [
        failed_item,
        RecognitionBatchItem(image_id="api-item-completed", status="completed"),
    ]

    with make_api_db_client(tmp_path, monkeypatch) as (client, db_session):
        db_session.add_all([failed_image, completed_image])
        db_session.add(
            Annotation(
                image_id="api-item-failed",
                caption="失败图片",
                tags="[]",
                objects="[]",
                model_used="mock",
            )
        )
        db_session.add(batch)
        db_session.commit()
        failed_item_id = failed_item.id

        response = client.get(
            "/api/recognition/batches/api-batch-items/items",
            params={"page": 1, "size": 50, "status": "failed"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["size"] == 50
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["id"] == failed_item_id
    assert item["image_id"] == "api-item-failed"
    assert item["status"] == "failed"
    assert item["error"] == "missing file"
    assert item["failure_category"] == "file_missing"
    assert "修复文件路径" in item["failure_hint"]
    assert item["image"] == {
        "id": "api-item-failed",
        "file_path": "/tmp/api-item-failed.png",
        "caption": "失败图片",
        "image_url": "/api/images/api-item-failed/file",
    }


def test_get_recognition_batch_items_returns_404_for_missing_batch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_api_db_client(tmp_path, monkeypatch) as (client, _db_session):
        response = client.get("/api/recognition/batches/missing-batch/items", params={"page": 1, "size": 50})

    assert response.status_code == 404
    assert response.json()["detail"] == "Batch not found"


def test_failed_batch_items_can_create_new_recognition_batch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    failed_image = Image(
        id="retry-failed-image",
        file_path="/tmp/retry-failed-image.png",
        file_hash="retry-failed-image-hash",
        file_size=100,
        width=32,
        height=24,
        format="PNG",
        created_at=now,
        modified_at=now,
        indexed_at=now,
    )
    completed_image = Image(
        id="retry-completed-image",
        file_path="/tmp/retry-completed-image.png",
        file_hash="retry-completed-image-hash",
        file_size=100,
        width=32,
        height=24,
        format="PNG",
        created_at=now,
        modified_at=now,
        indexed_at=now,
    )
    batch = RecognitionBatch(id="api-batch-retry", status="failed", total=2)
    batch.items = [
        RecognitionBatchItem(image_id="retry-failed-image", status="failed", error="boom"),
        RecognitionBatchItem(image_id="retry-completed-image", status="completed"),
    ]

    with make_api_db_client(tmp_path, monkeypatch) as (client, db_session):
        db_session.add_all([failed_image, completed_image, batch])
        db_session.commit()

        items_response = client.get(
            "/api/recognition/batches/api-batch-retry/items",
            params={"page": 1, "size": 50, "status": "failed"},
        )
        image_ids = [item["image_id"] for item in items_response.json()["items"]]
        create_response = client.post("/api/recognition/batches", json={"image_ids": image_ids})

    assert items_response.status_code == 200
    assert image_ids == ["retry-failed-image"]
    assert create_response.status_code == 202
    created = create_response.json()
    assert created["total"] == 1
    assert created["pending"] == 1
    assert created["status"] == "queued"


def test_post_recognition_batch_enqueues_and_get_returns_progress(api_client: TestClient):
    image_id = api_client.get("/api/images").json()["items"][0]["id"]

    create_response = api_client.post("/api/recognition/batches", json={"image_ids": [image_id]})

    assert create_response.status_code == 202
    created = create_response.json()
    assert set(created) == {
        "batch_id",
        "total",
        "completed",
        "failed",
        "pending",
        "running",
        "cancelled",
        "status",
        "created_at",
        "updated_at",
    }
    assert created["total"] == 1
    assert created["completed"] == 0
    assert created["failed"] == 0
    assert created["pending"] == 1
    assert created["running"] == 0
    assert created["cancelled"] == 0
    assert created["status"] == "queued"

    get_response = api_client.get(f"/api/recognition/batches/{created['batch_id']}")

    assert get_response.status_code == 200
    assert get_response.json() == created


def test_post_recognition_batch_rejects_missing_image_ids(api_client: TestClient):
    response = api_client.post("/api/recognition/batches", json={"image_ids": ["missing"]})

    assert response.status_code == 400
    assert response.json()["detail"] == "Batch contains unknown images"


def test_post_recognition_batch_accepts_folder_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/recognition/batches",
            json={"selection": {"folder": str((tmp_path / "travel").resolve())}},
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["total"] == 2
    assert payload["completed"] == 0
    assert payload["pending"] == 2
    assert payload["status"] == "queued"


def test_post_recognition_batch_accepts_selection_over_previous_batch_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch, extra_travel_images=199) as client:
        response = client.post("/api/recognition/batches", json={"selection": {"q": "旅行"}})

    assert response.status_code == 202
    payload = response.json()
    assert payload["total"] == 203
    assert payload["pending"] == 203
    assert payload["status"] == "queued"


def test_post_empty_recognition_batch_returns_400(api_client: TestClient):
    response = api_client.post("/api/recognition/batches", json={"image_ids": []})

    assert response.status_code == 400


def test_post_large_explicit_recognition_batch_is_queued(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch, extra_travel_images=195) as client:
        first_page = client.get("/api/images", params={"size": 100}).json()["items"]
        second_page = client.get("/api/images", params={"page": 2, "size": 100}).json()["items"]
        third_page = client.get("/api/images", params={"page": 3, "size": 100}).json()["items"]
        image_ids = [image["id"] for image in [*first_page, *second_page, *third_page]][:201]
        response = client.post("/api/recognition/batches", json={"image_ids": image_ids})

    assert response.status_code == 202
    payload = response.json()
    assert payload["total"] == 201
    assert payload["pending"] == 201
    assert payload["status"] == "queued"


def test_recognition_batch_control_endpoints_update_status(api_client: TestClient):
    image_id = api_client.get("/api/images").json()["items"][0]["id"]
    create_response = api_client.post("/api/recognition/batches", json={"image_ids": [image_id]})
    batch_id = create_response.json()["batch_id"]

    pause_response = api_client.post(f"/api/recognition/batches/{batch_id}/pause")
    resume_response = api_client.post(f"/api/recognition/batches/{batch_id}/resume")
    cancel_response = api_client.post(f"/api/recognition/batches/{batch_id}/cancel")

    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "queued"
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"
    assert cancel_response.json()["cancelled"] == 1


def test_missing_recognition_batch_control_returns_404(api_client: TestClient):
    response = api_client.post("/api/recognition/batches/missing/cancel")

    assert response.status_code == 404
    assert response.json()["detail"] == "Batch not found"


def test_get_missing_recognition_batch_returns_404(api_client: TestClient):
    response = api_client.get("/api/recognition/batches/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Batch not found"
