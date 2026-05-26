# PicMind Phase 1 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建 PicMind 的本地最小可跑链路：扫描配置目录中的图片，写入 SQLite 和 mock 标注，并通过 React 前端浏览图库、详情、统计和设置。

**架构：** 后端使用 FastAPI + SQLAlchemy + SQLite，启动时和手动触发时执行同步扫描。前端使用 React + Vite + TailwindCSS，通过 REST API 获取数据并用后端图片代理路由展示本地图片。

**技术栈：** Python 3.11、FastAPI、SQLAlchemy、Pydantic Settings、Pillow、pytest、React 18、Vite、TypeScript、TailwindCSS。

---

## 文件结构

### 后端

- 创建：`backend/pyproject.toml` — Python 项目依赖、测试配置和运行脚本。
- 创建：`backend/app/__init__.py` — 后端包标记。
- 创建：`backend/app/main.py` — FastAPI 应用入口、路由注册和启动扫描。
- 创建：`backend/app/config.py` — `.env` 配置读取，解析 `WATCH_FOLDERS` 和 `DB_PATH`。
- 创建：`backend/app/database.py` — SQLAlchemy engine、session 和表初始化。
- 创建：`backend/app/models.py` — `Image` 与 `Annotation` ORM 模型。
- 创建：`backend/app/schemas.py` — API 响应模型。
- 创建：`backend/app/services/scanner.py` — 遍历图片目录，筛选支持格式。
- 创建：`backend/app/services/indexer.py` — 计算 hash、读取图片元数据、去重入库。
- 创建：`backend/app/services/annotation.py` — 生成 Phase 1 mock 标注。
- 创建：`backend/app/api/images.py` — 图片列表、详情和图片文件代理接口。
- 创建：`backend/app/api/stats.py` — 统计接口。
- 创建：`backend/app/api/settings.py` — 设置接口。
- 创建：`backend/app/api/reindex.py` — 手动重新扫描接口。
- 创建：`backend/tests/conftest.py` — 测试数据库和临时图片 fixture。
- 创建：`backend/tests/test_scanner.py` — 扫描器测试。
- 创建：`backend/tests/test_indexer.py` — 去重和重扫测试。
- 创建：`backend/tests/test_api.py` — API 测试。

### 前端

- 创建：`frontend/package.json` — 前端依赖和脚本。
- 创建：`frontend/index.html` — Vite HTML 入口。
- 创建：`frontend/vite.config.ts` — Vite 配置。
- 创建：`frontend/tsconfig.json` — TypeScript 配置。
- 创建：`frontend/tailwind.config.js` — TailwindCSS 配置。
- 创建：`frontend/postcss.config.js` — PostCSS 配置。
- 创建：`frontend/src/main.tsx` — React 入口。
- 创建：`frontend/src/App.tsx` — 页面路由和布局。
- 创建：`frontend/src/index.css` — TailwindCSS 基础样式。
- 创建：`frontend/src/api/client.ts` — REST API 封装和类型定义。
- 创建：`frontend/src/pages/Gallery.tsx` — 图库页面。
- 创建：`frontend/src/pages/ImageDetail.tsx` — 图片详情页面。
- 创建：`frontend/src/pages/Dashboard.tsx` — 统计页面。
- 创建：`frontend/src/pages/Settings.tsx` — 设置与重新扫描页面。

### 项目根目录

- 创建：`.gitignore` — 忽略依赖、缓存、数据库和环境文件。
- 创建：`.env.example` — 后端配置示例。
- 保留：`docs/superpowers/specs/2026-05-23-picmind-phase-1-design.md` — 已批准规格。

---

### 任务 1：初始化后端项目和配置

**文件：**
- 创建：`backend/pyproject.toml`
- 创建：`backend/app/__init__.py`
- 创建：`backend/app/config.py`
- 创建：`backend/tests/test_config.py`
- 创建：`.gitignore`
- 创建：`.env.example`

- [x] **步骤 1：编写失败的配置测试**

创建 `backend/tests/test_config.py`：

```python
from pathlib import Path

from app.config import Settings


def test_settings_parses_watch_folders(tmp_path: Path):
    first = tmp_path / "photos"
    second = tmp_path / "screenshots"

    settings = Settings(
        watch_folders=f"{first},{second}",
        db_path=str(tmp_path / "picmind.db"),
    )

    assert settings.watch_folder_paths == [first, second]
    assert settings.db_path == tmp_path / "picmind.db"
```

- [x] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_config.py -v
```

预期：FAIL，报错包含 `ModuleNotFoundError: No module named 'app.config'` 或 `No module named 'app'`。

- [x] **步骤 3：创建后端依赖配置**

创建 `backend/pyproject.toml`：

```toml
[project]
name = "picmind-backend"
version = "0.1.0"
description = "Local intelligent image management backend"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy>=2.0.0",
    "pydantic-settings>=2.4.0",
    "pillow>=10.4.0",
    "python-multipart>=0.0.9",
]

[dependency-groups]
dev = [
    "httpx>=0.27.0",
    "pytest>=8.3.0",
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [x] **步骤 4：实现配置对象**

创建 `backend/app/__init__.py`：

```python
```

创建 `backend/app/config.py`：

```python
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    watch_folders: str = Field(default="", alias="WATCH_FOLDERS")
    db_path: Path = Field(default=Path("./data/picmind.db"), alias="DB_PATH")

    @property
    def watch_folder_paths(self) -> list[Path]:
        if not self.watch_folders.strip():
            return []
        return [Path(value.strip()) for value in self.watch_folders.split(",") if value.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

创建 `.gitignore`：

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
*.pyc
node_modules/
dist/
data/
*.db
*.sqlite
.claude/
```

创建 `.env.example`：

```dotenv
WATCH_FOLDERS=/absolute/path/to/photos,/absolute/path/to/screenshots
DB_PATH=./data/picmind.db
```

- [x] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && uv run pytest tests/test_config.py -v
```

预期：PASS，`1 passed`。

- [x] **步骤 6：Commit**

```bash
git add .gitignore .env.example backend/pyproject.toml backend/app/__init__.py backend/app/config.py backend/tests/test_config.py
git commit -m "chore: initialize backend configuration"
```

---

### 任务 2：实现数据库模型和 session

**文件：**
- 创建：`backend/app/database.py`
- 创建：`backend/app/models.py`
- 创建：`backend/tests/test_database.py`

- [x] **步骤 1：编写失败的数据库测试**

创建 `backend/tests/test_database.py`：

```python
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
```

- [x] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_database.py -v
```

预期：FAIL，报错包含 `ModuleNotFoundError: No module named 'app.database'`。

- [x] **步骤 3：实现数据库基础设施**

创建 `backend/app/database.py`：

```python
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def create_sqlite_engine(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})


engine = create_sqlite_engine(get_settings().db_path)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    import app.models

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [x] **步骤 4：实现 ORM 模型**

创建 `backend/app/models.py`：

```python
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (UniqueConstraint("file_hash", name="uq_images_file_hash"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    annotation: Mapped["Annotation"] = relationship(back_populates="image", uselist=False, cascade="all, delete-orphan")


class Annotation(Base):
    __tablename__ = "annotations"

    image_id: Mapped[str] = mapped_column(ForeignKey("images.id"), primary_key=True)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str] = mapped_column(Text, nullable=False)
    objects: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    model_used: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    image: Mapped[Image] = relationship(back_populates="annotation")
```

- [x] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && uv run pytest tests/test_database.py -v
```

预期：PASS，`1 passed`。

- [x] **步骤 6：Commit**

```bash
git add backend/app/database.py backend/app/models.py backend/tests/test_database.py
git commit -m "feat: add image metadata database models"
```

---

### 任务 3：实现扫描器和 mock 标注

**文件：**
- 创建：`backend/app/services/scanner.py`
- 创建：`backend/app/services/annotation.py`
- 创建：`backend/app/services/__init__.py`
- 创建：`backend/tests/test_scanner.py`
- 创建：`backend/tests/test_annotation.py`

- [x] **步骤 1：编写失败的扫描器测试**

创建 `backend/tests/test_scanner.py`：

```python
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
```

- [x] **步骤 2：编写失败的 mock 标注测试**

创建 `backend/tests/test_annotation.py`：

```python
from app.services.annotation import create_mock_annotation


def test_create_mock_annotation_returns_phase_one_values():
    annotation = create_mock_annotation()

    assert annotation.caption == "待分析的本地图片"
    assert annotation.tags == ["本地图片", "待分析"]
    assert annotation.objects == []
    assert annotation.model_used == "mock"
```

- [x] **步骤 3：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_scanner.py tests/test_annotation.py -v
```

预期：FAIL，报错包含 `No module named 'app.services'`。

- [x] **步骤 4：实现扫描器和 mock 标注**

创建 `backend/app/services/__init__.py`：

```python
```

创建 `backend/app/services/scanner.py`：

```python
from pathlib import Path

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


def find_image_files(folders: list[Path]) -> list[Path]:
    images: list[Path] = []
    for folder in folders:
        if not folder.exists() or not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                images.append(path)
    return sorted(images)
```

创建 `backend/app/services/annotation.py`：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class MockAnnotation:
    caption: str
    tags: list[str]
    objects: list[dict]
    model_used: str


def create_mock_annotation() -> MockAnnotation:
    return MockAnnotation(
        caption="待分析的本地图片",
        tags=["本地图片", "待分析"],
        objects=[],
        model_used="mock",
    )
```

- [x] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && uv run pytest tests/test_scanner.py tests/test_annotation.py -v
```

预期：PASS，`4 passed`。

- [x] **步骤 6：Commit**

```bash
git add backend/app/services/__init__.py backend/app/services/scanner.py backend/app/services/annotation.py backend/tests/test_scanner.py backend/tests/test_annotation.py
git commit -m "feat: add image scanning and mock annotations"
```

---

### 任务 4：实现索引服务

**文件：**
- 创建：`backend/app/services/indexer.py`
- 创建：`backend/tests/conftest.py`
- 创建：`backend/tests/test_indexer.py`

- [x] **步骤 1：编写失败的索引测试**

创建 `backend/tests/conftest.py`：

```python
from pathlib import Path

import pytest
from PIL import Image as PillowImage
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base


@pytest.fixture
def db_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    path = tmp_path / "sample.png"
    image = PillowImage.new("RGB", (32, 24), color="red")
    image.save(path)
    return path
```

创建 `backend/tests/test_indexer.py`：

```python
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
```

- [x] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_indexer.py -v
```

预期：FAIL，报错包含 `No module named 'app.services.indexer'`。

- [x] **步骤 3：实现索引服务**

创建 `backend/app/services/indexer.py`：

```python
from dataclasses import dataclass
from datetime import datetime
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
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                indexed_at=datetime.utcnow(),
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
                    created_at=datetime.utcnow(),
                )
            )
            db.commit()
            added += 1
        except Exception:
            db.rollback()
            errors += 1

    return IndexResult(added=added, skipped=skipped, errors=errors)
```

- [x] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && uv run pytest tests/test_indexer.py -v
```

预期：PASS，`2 passed`。

- [x] **步骤 5：Commit**

```bash
git add backend/app/services/indexer.py backend/tests/conftest.py backend/tests/test_indexer.py
git commit -m "feat: index local images into sqlite"
```

---

### 任务 5：实现后端 API

**文件：**
- 创建：`backend/app/schemas.py`
- 创建：`backend/app/api/__init__.py`
- 创建：`backend/app/api/images.py`
- 创建：`backend/app/api/stats.py`
- 创建：`backend/app/api/settings.py`
- 创建：`backend/app/api/reindex.py`
- 创建：`backend/app/main.py`
- 创建：`backend/tests/test_api.py`

- [x] **步骤 1：编写失败的 API 测试**

创建 `backend/tests/test_api.py`：

```python
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image as PillowImage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.services.indexer import index_folders


def create_client_with_image(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    image_path = tmp_path / "image.png"
    PillowImage.new("RGB", (16, 12), color="blue").save(image_path)

    session = SessionLocal()
    index_folders([tmp_path], session)
    session.close()

    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_get_images_returns_paginated_images(tmp_path: Path):
    client = create_client_with_image(tmp_path)

    response = client.get("/api/images")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["caption"] == "待分析的本地图片"
    assert data["items"][0]["tags"] == ["本地图片", "待分析"]


def test_get_stats_returns_counts(tmp_path: Path):
    client = create_client_with_image(tmp_path)

    response = client.get("/api/stats")

    assert response.status_code == 200
    assert response.json()["total_images"] == 1
    assert response.json()["formats"] == {"PNG": 1}


def test_get_settings_returns_phase_one_provider(tmp_path: Path):
    client = create_client_with_image(tmp_path)

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json()["provider"] == "mock"
```

- [x] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_api.py -v
```

预期：FAIL，报错包含 `No module named 'app.main'`。

- [x] **步骤 3：实现 schemas**

创建 `backend/app/schemas.py`：

```python
from datetime import datetime

from pydantic import BaseModel


class ImageItem(BaseModel):
    id: str
    file_path: str
    file_size: int
    width: int
    height: int
    format: str
    created_at: datetime
    modified_at: datetime
    indexed_at: datetime
    caption: str
    tags: list[str]
    image_url: str


class ImageList(BaseModel):
    items: list[ImageItem]
    total: int
    page: int
    size: int


class ImageDetail(ImageItem):
    objects: list[dict]
    model_used: str


class StatsResponse(BaseModel):
    total_images: int
    tags: dict[str, int]
    formats: dict[str, int]


class SettingsResponse(BaseModel):
    watch_folders: list[str]
    db_path: str
    provider: str


class ReindexResponse(BaseModel):
    added: int
    skipped: int
    errors: int
```

- [x] **步骤 4：实现 API 路由和应用入口**

创建 `backend/app/api/__init__.py`：

```python
```

创建 `backend/app/api/images.py`：

```python
from json import loads
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Image
from app.schemas import ImageDetail, ImageItem, ImageList

router = APIRouter(prefix="/api/images", tags=["images"])


def to_image_item(image: Image) -> ImageItem:
    return ImageItem(
        id=image.id,
        file_path=image.file_path,
        file_size=image.file_size,
        width=image.width,
        height=image.height,
        format=image.format,
        created_at=image.created_at,
        modified_at=image.modified_at,
        indexed_at=image.indexed_at,
        caption=image.annotation.caption,
        tags=loads(image.annotation.tags),
        image_url=f"/api/images/{image.id}/file",
    )


@router.get("", response_model=ImageList)
def list_images(page: int = 1, size: int = 50, tag: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Image).order_by(Image.indexed_at.desc())
    if tag:
        images = [image for image in query.all() if tag in loads(image.annotation.tags)]
        total = len(images)
        page_items = images[(page - 1) * size : page * size]
    else:
        total = query.count()
        page_items = query.offset((page - 1) * size).limit(size).all()
    return ImageList(items=[to_image_item(image) for image in page_items], total=total, page=page, size=size)


@router.get("/{image_id}", response_model=ImageDetail)
def get_image(image_id: str, db: Session = Depends(get_db)):
    image = db.get(Image, image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    item = to_image_item(image)
    return ImageDetail(**item.model_dump(), objects=loads(image.annotation.objects), model_used=image.annotation.model_used)


@router.get("/{image_id}/file")
def get_image_file(image_id: str, db: Session = Depends(get_db)):
    image = db.get(Image, image_id)
    if not image or not Path(image.file_path).is_file():
        raise HTTPException(status_code=404, detail="Image file not found")
    return FileResponse(image.file_path)
```

创建 `backend/app/api/stats.py`：

```python
from collections import Counter
from json import loads

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Image
from app.schemas import StatsResponse

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    images = db.query(Image).all()
    tag_counter: Counter[str] = Counter()
    format_counter: Counter[str] = Counter()
    for image in images:
        format_counter[image.format] += 1
        tag_counter.update(loads(image.annotation.tags))
    return StatsResponse(total_images=len(images), tags=dict(tag_counter), formats=dict(format_counter))
```

创建 `backend/app/api/settings.py`：

```python
from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas import SettingsResponse

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
def get_current_settings(settings: Settings = Depends(get_settings)):
    return SettingsResponse(
        watch_folders=[str(path) for path in settings.watch_folder_paths],
        db_path=str(settings.db_path),
        provider="mock",
    )
```

创建 `backend/app/api/reindex.py`：

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.schemas import ReindexResponse
from app.services.indexer import index_folders

router = APIRouter(prefix="/api/reindex", tags=["reindex"])


@router.post("", response_model=ReindexResponse)
def reindex(settings: Settings = Depends(get_settings), db: Session = Depends(get_db)):
    result = index_folders(settings.watch_folder_paths, db)
    return ReindexResponse(added=result.added, skipped=result.skipped, errors=result.errors)
```

创建 `backend/app/main.py`：

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.images import router as images_router
from app.api.reindex import router as reindex_router
from app.api.settings import router as settings_router
from app.api.stats import router as stats_router
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.services.indexer import index_folders

app = FastAPI(title="PicMind")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(images_router)
app.include_router(stats_router)
app.include_router(settings_router)
app.include_router(reindex_router)


@app.on_event("startup")
def startup() -> None:
    init_db()
    settings = get_settings()
    db = SessionLocal()
    try:
        index_folders(settings.watch_folder_paths, db)
    finally:
        db.close()
```

- [x] **步骤 5：运行 API 测试验证通过**

运行：

```bash
cd backend && uv run pytest tests/test_api.py -v
```

预期：PASS，`3 passed`。

- [x] **步骤 6：运行全部后端测试**

运行：

```bash
cd backend && uv run pytest -v
```

预期：PASS，所有测试通过。

- [x] **步骤 7：Commit**

```bash
git add backend/app/schemas.py backend/app/api backend/app/main.py backend/tests/test_api.py
git commit -m "feat: expose image gallery api"
```

---

### 任务 6：初始化前端项目和 API 客户端

**文件：**
- 创建：`frontend/package.json`
- 创建：`frontend/index.html`
- 创建：`frontend/vite.config.ts`
- 创建：`frontend/tsconfig.json`
- 创建：`frontend/tailwind.config.js`
- 创建：`frontend/postcss.config.js`
- 创建：`frontend/src/main.tsx`
- 创建：`frontend/src/index.css`
- 创建：`frontend/src/api/client.ts`

- [x] **步骤 1：创建前端项目配置**

创建 `frontend/package.json`：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@vitejs/plugin-react": "latest",
    "vite": "latest",
    "typescript": "latest",
    "react": "latest",
    "react-dom": "latest",
    "lucide-react": "latest"
  },
  "devDependencies": {
    "tailwindcss": "latest",
    "postcss": "latest",
    "autoprefixer": "latest",
    "@types/react": "latest",
    "@types/react-dom": "latest"
  }
}
```

创建 `frontend/index.html`：

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PicMind</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

创建 `frontend/vite.config.ts`：

```typescript
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
});
```

创建 `frontend/tsconfig.json`：

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"]
}
```

创建 `frontend/tailwind.config.js`：

```javascript
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
};
```

创建 `frontend/postcss.config.js`：

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [x] **步骤 2：创建前端入口和 API 客户端**

创建 `frontend/src/index.css`：

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  background: #f8fafc;
  color: #0f172a;
}
```

创建 `frontend/src/api/client.ts`：

```typescript
export type ImageItem = {
  id: string;
  file_path: string;
  file_size: number;
  width: number;
  height: number;
  format: string;
  created_at: string;
  modified_at: string;
  indexed_at: string;
  caption: string;
  tags: string[];
  image_url: string;
};

export type ImageDetail = ImageItem & {
  objects: Record<string, unknown>[];
  model_used: string;
};

export type ImageList = {
  items: ImageItem[];
  total: number;
  page: number;
  size: number;
};

export type Stats = {
  total_images: number;
  tags: Record<string, number>;
  formats: Record<string, number>;
};

export type Settings = {
  watch_folders: string[];
  db_path: string;
  provider: string;
};

export type ReindexResult = {
  added: number;
  skipped: number;
  errors: number;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listImages: (page = 1, size = 50, tag?: string) => {
    const params = new URLSearchParams({ page: String(page), size: String(size) });
    if (tag) params.set('tag', tag);
    return request<ImageList>(`/api/images?${params}`);
  },
  getImage: (id: string) => request<ImageDetail>(`/api/images/${id}`),
  getStats: () => request<Stats>('/api/stats'),
  getSettings: () => request<Settings>('/api/settings'),
  reindex: () => request<ReindexResult>('/api/reindex', { method: 'POST' }),
};
```

创建 `frontend/src/main.tsx`：

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [x] **步骤 3：运行前端依赖安装**

运行：

```bash
cd frontend && npm install
```

预期：生成 `package-lock.json`，命令退出码为 0。

- [x] **步骤 4：Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/index.html frontend/vite.config.ts frontend/tsconfig.json frontend/tailwind.config.js frontend/postcss.config.js frontend/src/main.tsx frontend/src/index.css frontend/src/api/client.ts
git commit -m "chore: initialize frontend application"
```

---

### 任务 7：实现前端页面

**文件：**
- 创建：`frontend/src/App.tsx`
- 创建：`frontend/src/pages/Gallery.tsx`
- 创建：`frontend/src/pages/ImageDetail.tsx`
- 创建：`frontend/src/pages/Dashboard.tsx`
- 创建：`frontend/src/pages/Settings.tsx`

- [x] **步骤 1：实现 App 导航和页面切换**

创建 `frontend/src/App.tsx`：

```typescript
import { useState } from 'react';
import Dashboard from './pages/Dashboard';
import Gallery from './pages/Gallery';
import ImageDetail from './pages/ImageDetail';
import Settings from './pages/Settings';

type Page = 'gallery' | 'dashboard' | 'settings';

export default function App() {
  const [page, setPage] = useState<Page>('gallery');
  const [selectedImageId, setSelectedImageId] = useState<string | null>(null);

  if (selectedImageId) {
    return <ImageDetail imageId={selectedImageId} onBack={() => setSelectedImageId(null)} />;
  }

  return (
    <div className="min-h-screen">
      <header className="border-b bg-white px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">PicMind</h1>
            <p className="text-sm text-slate-500">本地图片智能管理系统</p>
          </div>
          <nav className="flex gap-2">
            {(['gallery', 'dashboard', 'settings'] as Page[]).map((item) => (
              <button
                key={item}
                onClick={() => setPage(item)}
                className={`rounded-lg px-4 py-2 text-sm ${page === item ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700'}`}
              >
                {item === 'gallery' ? '图库' : item === 'dashboard' ? '看板' : '设置'}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        {page === 'gallery' && <Gallery onSelectImage={setSelectedImageId} />}
        {page === 'dashboard' && <Dashboard />}
        {page === 'settings' && <Settings />}
      </main>
    </div>
  );
}
```

- [x] **步骤 2：实现 Gallery 页面**

创建 `frontend/src/pages/Gallery.tsx`：

```typescript
import { useEffect, useState } from 'react';
import { api, ImageItem } from '../api/client';

export default function Gallery({ onSelectImage }: { onSelectImage: (id: string) => void }) {
  const [images, setImages] = useState<ImageItem[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listImages()
      .then((data) => {
        setImages(data.items);
        setTotal(data.total);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  if (error) return <p className="text-red-600">加载失败：{error}</p>;

  return (
    <section>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h2 className="text-xl font-semibold">图库</h2>
          <p className="text-sm text-slate-500">共 {total} 张图片</p>
        </div>
      </div>
      {images.length === 0 ? (
        <div className="rounded-xl border border-dashed bg-white p-10 text-center text-slate-500">暂无图片，请在设置的目录中添加图片后重新扫描。</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {images.map((image) => (
            <button key={image.id} onClick={() => onSelectImage(image.id)} className="overflow-hidden rounded-xl bg-white text-left shadow-sm transition hover:shadow-md">
              <img src={image.image_url} alt={image.caption} className="h-44 w-full object-cover" />
              <div className="p-3">
                <p className="line-clamp-2 text-sm font-medium">{image.caption}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {image.tags.map((tag) => (
                    <span key={tag} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{tag}</span>
                  ))}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
```

- [x] **步骤 3：实现详情、看板和设置页面**

创建 `frontend/src/pages/ImageDetail.tsx`：

```typescript
import { useEffect, useState } from 'react';
import { api, ImageDetail as ImageDetailType } from '../api/client';

export default function ImageDetail({ imageId, onBack }: { imageId: string; onBack: () => void }) {
  const [image, setImage] = useState<ImageDetailType | null>(null);

  useEffect(() => {
    api.getImage(imageId).then(setImage);
  }, [imageId]);

  if (!image) return <div className="p-8">加载中……</div>;

  return (
    <main className="mx-auto max-w-5xl px-6 py-8">
      <button onClick={onBack} className="mb-4 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">返回图库</button>
      <div className="grid gap-6 lg:grid-cols-[2fr,1fr]">
        <img src={image.image_url} alt={image.caption} className="w-full rounded-xl bg-white object-contain shadow-sm" />
        <aside className="rounded-xl bg-white p-5 shadow-sm">
          <h2 className="text-xl font-semibold">图片详情</h2>
          <p className="mt-4 text-slate-700">{image.caption}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {image.tags.map((tag) => <span key={tag} className="rounded-full bg-slate-100 px-3 py-1 text-sm">{tag}</span>)}
          </div>
          <dl className="mt-6 space-y-2 text-sm text-slate-600">
            <div><dt className="font-medium text-slate-900">尺寸</dt><dd>{image.width} × {image.height}</dd></div>
            <div><dt className="font-medium text-slate-900">格式</dt><dd>{image.format}</dd></div>
            <div><dt className="font-medium text-slate-900">文件大小</dt><dd>{image.file_size} 字节</dd></div>
            <div><dt className="font-medium text-slate-900">路径</dt><dd className="break-all">{image.file_path}</dd></div>
            <div><dt className="font-medium text-slate-900">模型</dt><dd>{image.model_used}</dd></div>
          </dl>
        </aside>
      </div>
    </main>
  );
}
```

创建 `frontend/src/pages/Dashboard.tsx`：

```typescript
import { useEffect, useState } from 'react';
import { api, Stats } from '../api/client';

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    api.getStats().then(setStats);
  }, []);

  if (!stats) return <p>加载中……</p>;

  return (
    <section className="space-y-6">
      <h2 className="text-xl font-semibold">统计看板</h2>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">图片总数</p><p className="mt-2 text-3xl font-bold">{stats.total_images}</p></div>
        <div className="rounded-xl bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">标签种类</p><p className="mt-2 text-3xl font-bold">{Object.keys(stats.tags).length}</p></div>
        <div className="rounded-xl bg-white p-5 shadow-sm"><p className="text-sm text-slate-500">格式种类</p><p className="mt-2 text-3xl font-bold">{Object.keys(stats.formats).length}</p></div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl bg-white p-5 shadow-sm"><h3 className="font-semibold">标签 Top</h3>{Object.entries(stats.tags).map(([name, count]) => <p key={name} className="mt-2 flex justify-between text-sm"><span>{name}</span><span>{count}</span></p>)}</div>
        <div className="rounded-xl bg-white p-5 shadow-sm"><h3 className="font-semibold">格式分布</h3>{Object.entries(stats.formats).map(([name, count]) => <p key={name} className="mt-2 flex justify-between text-sm"><span>{name}</span><span>{count}</span></p>)}</div>
      </div>
    </section>
  );
}
```

创建 `frontend/src/pages/Settings.tsx`：

```typescript
import { useEffect, useState } from 'react';
import { api, ReindexResult, Settings as SettingsType } from '../api/client';

export default function Settings() {
  const [settings, setSettings] = useState<SettingsType | null>(null);
  const [result, setResult] = useState<ReindexResult | null>(null);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    api.getSettings().then(setSettings);
  }, []);

  async function reindex() {
    setScanning(true);
    try {
      setResult(await api.reindex());
    } finally {
      setScanning(false);
    }
  }

  if (!settings) return <p>加载中……</p>;

  return (
    <section className="space-y-6">
      <h2 className="text-xl font-semibold">设置</h2>
      <div className="rounded-xl bg-white p-5 shadow-sm">
        <p className="text-sm text-slate-500">监听目录</p>
        <ul className="mt-2 list-disc pl-5 text-sm">{settings.watch_folders.map((folder) => <li key={folder}>{folder}</li>)}</ul>
        <p className="mt-4 text-sm text-slate-500">数据库：{settings.db_path}</p>
        <p className="mt-2 text-sm text-slate-500">Provider：{settings.provider}</p>
        <button disabled={scanning} onClick={reindex} className="mt-5 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">{scanning ? '扫描中……' : '重新扫描'}</button>
        {result && <p className="mt-4 text-sm text-slate-600">新增 {result.added}，跳过 {result.skipped}，错误 {result.errors}</p>}
      </div>
    </section>
  );
}
```

- [x] **步骤 4：运行前端构建验证**

运行：

```bash
cd frontend && npm run build
```

预期：PASS，生成 `frontend/dist`。

- [x] **步骤 5：Commit**

```bash
git add frontend/src/App.tsx frontend/src/pages
git commit -m "feat: add picmind gallery interface"
```

---

### 任务 8：端到端本地验证和文档提交

**文件：**
- 修改：`docs/superpowers/plans/2026-05-23-picmind-phase-1.md`
- 已创建：`docs/superpowers/specs/2026-05-23-picmind-phase-1-design.md`

- [x] **步骤 1：准备本地测试图片目录**

运行：

```bash
mkdir -p data/sample-photos
```

创建一张测试图片：

```bash
cd backend && uv run python - <<'PY'
from pathlib import Path
from PIL import Image
path = Path('../data/sample-photos/sample.png')
path.parent.mkdir(parents=True, exist_ok=True)
Image.new('RGB', (80, 60), color='green').save(path)
PY
```

- [x] **步骤 2：配置后端 `.env`**

创建 `backend/.env`：

```dotenv
WATCH_FOLDERS=../data/sample-photos
DB_PATH=../data/picmind.db
```

- [x] **步骤 3：运行后端测试和前端构建**

运行：

```bash
cd backend && uv run pytest -v
```

预期：PASS，所有后端测试通过。

运行：

```bash
cd frontend && npm run build
```

预期：PASS，生成生产构建。

- [x] **步骤 4：启动后端和前端进行手动验证**

启动后端：

```bash
cd backend && uv run uvicorn app.main:app --reload
```

另一个终端启动前端：

```bash
cd frontend && npm run dev
```

在浏览器打开 Vite 输出的本地地址，验证：

- 图库显示 `sample.png`。
- 点击图片能进入详情页。
- 详情页显示 `待分析的本地图片` 和标签。
- Dashboard 显示图片总数为 `1`。
- Settings 页面点击「重新扫描」后显示新增 `0`，跳过 `1`，错误 `0`。

- [x] **步骤 5：Commit 规格和计划文档**

```bash
git add docs/superpowers/specs/2026-05-23-picmind-phase-1-design.md docs/superpowers/plans/2026-05-23-picmind-phase-1.md
git commit -m "docs: add picmind phase one plan"
```

---

## Phase 1 本地验证记录

- 后端测试：`cd backend && uv run pytest -v`，结果为 22 passed。
- 前端构建：`cd frontend && npm run build`，结果为 Vite production build 成功。
- 本地服务：后端 `http://127.0.0.1:8000` 启动成功；前端 dev server 启动成功，因 `5173` 被占用自动使用 `http://127.0.0.1:5174/`。
- 端到端接口验证：图库返回 1 张 `sample.png`；图片文件代理返回 PNG；详情返回 mock 标注；统计返回 `total_images = 1` 和 `formats = {"PNG": 1}`；`POST /api/reindex` 返回 `added = 0`、`skipped = 1`、`errors = 0`。
- 说明：命令行输出中的中文 caption / tags 受 Windows 控制台编码影响显示为乱码，但断言使用 Python 字符串比较通过。

---

## 自检结果

- 规格覆盖度：本计划覆盖配置读取、启动扫描、手动重扫、hash 去重、SQLite 数据模型、mock annotation、图片列表、详情、统计、设置、前端页面和测试。
- 占位符扫描：计划不包含未完成章节、占位说明或未定义的后续任务。
- 类型一致性：后端 API 响应类型与前端 `client.ts` 类型一致，`Image`、`Annotation`、`IndexResult`、`Settings` 等名称在定义和引用中保持一致。
