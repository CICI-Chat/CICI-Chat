# PicMind Phase 3 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为 PicMind 图库增加服务端关键词搜索、标签/格式筛选、排序控制，并在设置页清晰展示只读识别 Provider 状态。

**架构：** 后端在现有 `/api/images` endpoint 中扩展 SQLAlchemy 查询，不新增搜索服务，使用白名单排序字段和绑定参数过滤用户输入。前端在 `Gallery` 内维护筛选表单、已提交查询和选择状态，通过扩展后的 API 客户端序列化查询参数；设置页新增只读 Provider 卡片。为满足从详情页返回保留筛选状态，`App` 改为在详情页打开时隐藏而不是卸载 `Gallery`。

**技术栈：** Python 3.11、FastAPI、SQLAlchemy、SQLite、pytest、React、TypeScript、Vite、TailwindCSS。

---

## 文件结构

### 后端

- 修改：`backend/tests/test_api.py` — 增加图库查询测试数据 helper，覆盖 `q` 匹配 caption/tags/file_path、`format` 筛选、`tag + q` 组合、排序、非法 sort/order。
- 修改：`backend/app/api/images.py` — 扩展 `list_images` 查询参数，使用 `outerjoin`/`joinedload` 查询 annotation，执行服务端搜索、筛选、排序和分页。

### 前端

- 修改：`frontend/src/api/client.ts` — 增加 `ImageListParams` 类型，让 `api.listImages` 支持 `q`、`tag`、`format`、`sort`、`order`。
- 修改：`frontend/src/pages/Gallery.tsx` — 增加检索工具栏、筛选状态、下拉选项派生、清空筛选、空结果状态、筛选变化后清空已选择图片。
- 修改：`frontend/src/App.tsx` — 保持 `Gallery` 挂载，详情页打开时用 `hidden` 隐藏主应用壳，从详情返回时保留 Gallery 内部状态。
- 修改：`frontend/src/pages/Settings.tsx` — 新增「识别 Provider」只读卡片，说明当前 Provider 为 `mock`、Phase 3 不支持页面切换。

---

## 任务拆分

### 任务 1：后端图库查询测试

**文件：**
- 修改：`backend/tests/test_api.py`

- [ ] **步骤 1：编写失败的后端 API 测试**

在 `backend/tests/test_api.py` 顶部把现有 imports 改成：

```python
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
from app.models import Annotation, Image
from app.services.indexer import index_folders
```

在 `make_api_client` fixture 之后、`api_client` fixture 之前添加测试数据 helper：

```python
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
def make_gallery_query_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.config import Settings
    from app.database import get_db
    from app.main import create_app

    tmp_path.mkdir(parents=True, exist_ok=True)
    test_settings = Settings(watch_folders=str(tmp_path), db_path=tmp_path / "gallery-query.db")
    monkeypatch.setattr("app.api.reindex.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.api.settings.get_settings", lambda: test_settings)
    app = create_app(run_startup_indexing=False)

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
```

在 `test_get_images_returns_indexed_image_with_mock_annotation` 后添加这些测试：

```python
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


def test_list_images_searches_file_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/images", params={"q": "mountain"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["caption"] for item in payload["items"]] == ["雪山日出"]


def test_list_images_filters_format(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with make_gallery_query_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/images", params={"format": "PNG", "sort": "file_size", "order": "asc"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [item["caption"] for item in payload["items"]] == ["家庭相册", "雪山日出"]


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
    assert [item["caption"] for item in payload["items"]] == ["雪山日出", "家庭相册", "城市夜景"]


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
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_api.py -v
```

预期：新增测试失败，至少包含 `assert payload["total"] == 1` 失败或非法 sort/order 返回 200 而不是 400，因为 `backend/app/api/images.py` 还没有实现 `q`、`format`、`sort`、`order`。

- [ ] **步骤 3：Commit 失败测试**

```bash
git add backend/tests/test_api.py
git commit -m "test(PicMind): cover gallery search filters"
```

### 任务 2：实现后端服务端查询

**文件：**
- 修改：`backend/app/api/images.py`
- 测试：`backend/tests/test_api.py`

- [ ] **步骤 1：实现安全的查询参数和 SQLAlchemy 查询**

把 `backend/app/api/images.py` 的 imports 改成：

```python
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import asc, desc, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Annotation, Image
from app.schemas import ImageDetail, ImageItem, ImageList
```

在 `to_image_detail` 后、`@router.get` 前添加排序白名单：

```python
SORT_COLUMNS = {
    "indexed_at": Image.indexed_at,
    "modified_at": Image.modified_at,
    "file_size": Image.file_size,
    "width": Image.width,
    "height": Image.height,
}
```

把 `list_images` 函数整体替换为：

```python
@router.get("", response_model=ImageList)
def list_images(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    tag: str | None = None,
    q: str | None = None,
    image_format: str | None = Query(default=None, alias="format"),
    sort: str = "indexed_at",
    order: str = "desc",
    db: Session = Depends(get_db),
) -> ImageList:
    sort_column = SORT_COLUMNS.get(sort)
    if sort_column is None:
        raise HTTPException(status_code=400, detail="Unsupported sort field")
    if order not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="Unsupported sort order")

    query = db.query(Image).outerjoin(Annotation).options(joinedload(Image.annotation))

    search_text = q.strip() if q else ""
    if search_text:
        search_pattern = f"%{search_text}%"
        query = query.filter(
            or_(
                Image.file_path.ilike(search_pattern),
                Annotation.caption.ilike(search_pattern),
                Annotation.tags.ilike(search_pattern),
            )
        )

    if tag is not None:
        tag_text = tag.strip()
        if tag_text:
            query = query.filter(Annotation.tags.ilike(f'%"{tag_text}"%'))

    if image_format is not None:
        format_text = image_format.strip()
        if format_text:
            query = query.filter(Image.format == format_text)

    total = query.count()
    order_by = asc(sort_column) if order == "asc" else desc(sort_column)
    images = query.order_by(order_by).offset((page - 1) * size).limit(size).all()
    return ImageList(items=[to_image_item(image) for image in images], total=total, page=page, size=size)
```

- [ ] **步骤 2：运行后端 API 测试验证通过**

运行：

```bash
cd backend && uv run pytest tests/test_api.py -v
```

预期：`tests/test_api.py` 全部 PASS。

- [ ] **步骤 3：运行后端完整测试防回退**

运行：

```bash
cd backend && uv run pytest -q
```

预期：全部 PASS，Phase 2 的单张识别和批量识别测试仍通过。

- [ ] **步骤 4：Commit 后端实现**

```bash
git add backend/app/api/images.py
git commit -m "feat(PicMind): add gallery server search filters"
```

### 任务 3：扩展前端 API 客户端

**文件：**
- 修改：`frontend/src/api/client.ts`

- [ ] **步骤 1：新增查询参数类型并改造 `listImages`**

在 `ImageList` type 后添加：

```ts
export type ImageListParams = {
  page?: number;
  size?: number;
  q?: string;
  tag?: string;
  format?: string;
  sort?: 'indexed_at' | 'modified_at' | 'file_size' | 'width' | 'height';
  order?: 'asc' | 'desc';
};
```

把 `api.listImages` 替换为：

```ts
  listImages: (params: ImageListParams = {}) => {
    const searchParams = new URLSearchParams({
      page: String(params.page ?? 1),
      size: String(params.size ?? 50),
    });
    if (params.q) searchParams.set('q', params.q);
    if (params.tag) searchParams.set('tag', params.tag);
    if (params.format) searchParams.set('format', params.format);
    if (params.sort) searchParams.set('sort', params.sort);
    if (params.order) searchParams.set('order', params.order);
    return request<ImageList>(`/api/images?${searchParams}`);
  },
```

- [ ] **步骤 2：运行前端构建验证类型通过**

运行：

```bash
cd frontend && npm run build
```

预期：TypeScript 和 Vite build PASS。

- [ ] **步骤 3：Commit API 客户端**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(PicMind): add gallery query api client"
```

### 任务 4：实现图库检索工具栏和筛选行为

**文件：**
- 修改：`frontend/src/pages/Gallery.tsx`

- [ ] **步骤 1：更新 imports 和类型**

把文件顶部 imports 改成：

```ts
import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { api, ImageItem, ImageListParams, RecognitionBatch } from '../api/client';
```

在 `isBatchActive` 下面添加类型和默认值：

```ts
type SortField = NonNullable<ImageListParams['sort']>;
type SortOrder = NonNullable<ImageListParams['order']>;

type GalleryFilters = {
  q: string;
  tag: string;
  format: string;
  sort: SortField;
  order: SortOrder;
};

const defaultFilters: GalleryFilters = {
  q: '',
  tag: '',
  format: '',
  sort: 'indexed_at',
  order: 'desc',
};
```

- [ ] **步骤 2：新增筛选状态、派生下拉选项和加载逻辑**

在 `Gallery` 组件中 `const [total, setTotal] = useState(0);` 后添加：

```ts
  const [filters, setFilters] = useState<GalleryFilters>(defaultFilters);
  const [draftQuery, setDraftQuery] = useState('');
```

把 `loadGallery` 替换为：

```ts
  const loadGallery = useCallback(() => {
    setError(null);
    api
      .listImages({
        q: filters.q || undefined,
        tag: filters.tag || undefined,
        format: filters.format || undefined,
        sort: filters.sort,
        order: filters.order,
      })
      .then((data) => {
        setImages(data.items);
        setTotal(data.total);
      })
      .catch((err: Error) => setError(err.message));
  }, [filters]);
```

在 `useEffect(() => { loadGallery(); }, [loadGallery]);` 后添加：

```ts
  const tagOptions = useMemo(
    () => Array.from(new Set(images.flatMap((image) => image.tags))).sort((left, right) => left.localeCompare(right)),
    [images],
  );

  const formatOptions = useMemo(
    () => Array.from(new Set(images.map((image) => image.format))).sort((left, right) => left.localeCompare(right)),
    [images],
  );

  const hasActiveFilters = Boolean(filters.q || filters.tag || filters.format || filters.sort !== 'indexed_at' || filters.order !== 'desc');
```

- [ ] **步骤 3：新增筛选事件处理函数**

在 `toggleSelected` 函数前添加：

```ts
  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSelectedIds([]);
    setFilters((current) => ({ ...current, q: draftQuery.trim() }));
  };

  const updateFilter = <Key extends keyof GalleryFilters>(key: Key, value: GalleryFilters[Key]) => {
    setSelectedIds([]);
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const clearFilters = () => {
    setSelectedIds([]);
    setDraftQuery('');
    setFilters(defaultFilters);
  };
```

- [ ] **步骤 4：替换图库顶部布局为两行工具栏**

把 `<section>` 内从顶部 `<div className="mb-6...">` 到其 closing `</div>` 替换为：

```tsx
      <div className="mb-6 space-y-4 rounded-xl bg-white p-4 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-xl font-semibold">图库</h2>
            <p className="text-sm text-slate-500">共 {total} 张图片</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-500">已选择 {selectedIds.length} 张</span>
            <button
              type="button"
              onClick={startBatchRecognition}
              disabled={selectedIds.length === 0 || batchActive || batchSubmitting}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              批量识别
            </button>
          </div>
        </div>

        <form onSubmit={submitSearch} className="flex flex-col gap-3 sm:flex-row">
          <input
            value={draftQuery}
            onChange={(event) => setDraftQuery(event.target.value)}
            placeholder="搜索标题、标签或路径"
            className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400"
          />
          <button type="submit" className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">
            搜索
          </button>
          <button
            type="button"
            onClick={clearFilters}
            disabled={!hasActiveFilters}
            className="rounded-lg bg-slate-100 px-4 py-2 text-sm text-slate-700 disabled:cursor-not-allowed disabled:text-slate-400"
          >
            清空筛选
          </button>
        </form>

        <div className="grid gap-3 md:grid-cols-4">
          <label className="text-sm text-slate-600">
            标签筛选
            <select
              value={filters.tag}
              onChange={(event) => updateFilter('tag', event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">全部标签</option>
              {tagOptions.map((tag) => (
                <option key={tag} value={tag}>{tag}</option>
              ))}
            </select>
          </label>

          <label className="text-sm text-slate-600">
            格式筛选
            <select
              value={filters.format}
              onChange={(event) => updateFilter('format', event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">全部格式</option>
              {formatOptions.map((format) => (
                <option key={format} value={format}>{format}</option>
              ))}
            </select>
          </label>

          <label className="text-sm text-slate-600">
            排序字段
            <select
              value={filters.sort}
              onChange={(event) => updateFilter('sort', event.target.value as SortField)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="indexed_at">入库时间</option>
              <option value="modified_at">修改时间</option>
              <option value="file_size">文件大小</option>
              <option value="width">宽度</option>
              <option value="height">高度</option>
            </select>
          </label>

          <label className="text-sm text-slate-600">
            排序方向
            <select
              value={filters.order}
              onChange={(event) => updateFilter('order', event.target.value as SortOrder)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="desc">降序</option>
              <option value="asc">升序</option>
            </select>
          </label>
        </div>
      </div>
```

- [ ] **步骤 5：替换空状态文案**

把当前空状态：

```tsx
        <div className="rounded-xl border border-dashed bg-white p-10 text-center text-slate-500">暂无图片，请在设置的目录中添加图片后重新扫描。</div>
```

替换为：

```tsx
        <div className="rounded-xl border border-dashed bg-white p-10 text-center text-slate-500">
          <p>{hasActiveFilters ? '没有匹配的图片' : '暂无图片，请在设置的目录中添加图片后重新扫描。'}</p>
          {hasActiveFilters && (
            <button type="button" onClick={clearFilters} className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white">
              清空筛选
            </button>
          )}
        </div>
```

- [ ] **步骤 6：运行前端构建验证通过**

运行：

```bash
cd frontend && npm run build
```

预期：TypeScript 和 Vite build PASS。

- [ ] **步骤 7：Commit 图库 UI**

```bash
git add frontend/src/pages/Gallery.tsx
git commit -m "feat(PicMind): add gallery search toolbar"
```

### 任务 5：保留详情页返回后的图库筛选状态

**文件：**
- 修改：`frontend/src/App.tsx`
- 验证：`frontend/src/pages/Gallery.tsx`

- [ ] **步骤 1：改造 App 让 Gallery 不因详情页卸载**

把 `App` 组件中这一段删除：

```tsx
  if (selectedImageId) {
    return <ImageDetail imageId={selectedImageId} onBack={() => setSelectedImageId(null)} />;
  }
```

把 `return (...)` 的内容替换为：

```tsx
  return (
    <>
      {selectedImageId && <ImageDetail imageId={selectedImageId} onBack={() => setSelectedImageId(null)} />}
      <div className={`min-h-screen ${selectedImageId ? 'hidden' : ''}`}>
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
    </>
  );
```

- [ ] **步骤 2：运行前端构建验证通过**

运行：

```bash
cd frontend && npm run build
```

预期：TypeScript 和 Vite build PASS。

- [ ] **步骤 3：Commit 导航状态保留**

```bash
git add frontend/src/App.tsx
git commit -m "fix(PicMind): preserve gallery filters on detail return"
```

### 任务 6：设置页展示 Provider 配置骨架

**文件：**
- 修改：`frontend/src/pages/Settings.tsx`

- [ ] **步骤 1：拆分设置页卡片并新增 Provider 卡片**

把 `return` 中 `<section className="space-y-6">` 的内部替换为：

```tsx
      <h2 className="text-xl font-semibold">设置</h2>

      <div className="rounded-xl bg-white p-5 shadow-sm">
        <p className="text-sm text-slate-500">监听目录</p>
        <ul className="mt-2 list-disc pl-5 text-sm">{settings.watch_folders.map((folder) => <li key={folder}>{folder}</li>)}</ul>
        <p className="mt-4 text-sm text-slate-500">数据库：{settings.db_path}</p>
        <button disabled={scanning} onClick={reindex} className="mt-5 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50">{scanning ? '扫描中……' : '重新扫描'}</button>
        {error && <p className="mt-4 text-sm text-red-600">扫描失败：{error}</p>}
        {result && <p className="mt-4 text-sm text-slate-600">新增 {result.added}，跳过 {result.skipped}，错误 {result.errors}</p>}
      </div>

      <div className="rounded-xl bg-white p-5 shadow-sm">
        <p className="text-sm text-slate-500">识别 Provider</p>
        <div className="mt-3 flex flex-col gap-3 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
          <p><span className="font-medium text-slate-900">当前 Provider：</span>{settings.provider}</p>
          <p>当前阶段使用本地 Mock 识别，用于验证图片识别、结果持久化和批量流程。</p>
          <p>后续可将 Provider 替换为 Ollama 或云端视觉模型。</p>
          <p className="font-medium text-amber-700">Phase 3 不支持在页面切换 Provider。</p>
        </div>
      </div>
```

- [ ] **步骤 2：运行前端构建验证通过**

运行：

```bash
cd frontend && npm run build
```

预期：TypeScript 和 Vite build PASS。

- [ ] **步骤 3：Commit 设置页 Provider 卡片**

```bash
git add frontend/src/pages/Settings.tsx
git commit -m "feat(PicMind): show recognition provider settings"
```

### 任务 7：最终验证

**文件：**
- 修改：`docs/superpowers/plans/2026-05-29-picmind-phase-3.md`

- [ ] **步骤 1：运行后端完整测试**

运行：

```bash
cd backend && uv run pytest -q
```

预期：全部 PASS；应覆盖图库查询、图片详情、单张识别、批量识别、设置、统计、扫描和数据库测试。

- [ ] **步骤 2：运行前端生产构建**

运行：

```bash
cd frontend && npm run build
```

预期：TypeScript 和 Vite build PASS。

- [ ] **步骤 3：手动验证后端 API**

启动后端：

```bash
cd backend && uv run uvicorn app.main:app --reload
```

在另一个终端验证：

```bash
curl "http://127.0.0.1:8000/api/images?q=%E5%9B%BE%E7%89%87&sort=indexed_at&order=desc"
curl "http://127.0.0.1:8000/api/images?format=PNG"
curl "http://127.0.0.1:8000/api/images?sort=caption"
curl "http://127.0.0.1:8000/api/images?order=sideways"
curl "http://127.0.0.1:8000/api/settings"
```

预期：前两个 `/api/images` 返回 200 和 `items/total/page/size`；非法 `sort` 返回 400 且 `detail` 为 `Unsupported sort field`；非法 `order` 返回 400 且 `detail` 为 `Unsupported sort order`；`/api/settings` 返回 `provider: "mock"`。

- [ ] **步骤 4：手动验证前端 UI**

启动前端：

```bash
cd frontend && npm run dev
```

浏览器打开 Vite dev server 后验证：

1. 图库顶部显示搜索框、搜索按钮、清空筛选、标签筛选、格式筛选、排序字段、排序方向。
2. 在搜索框输入当前图库中存在的 caption/tag/file_path 片段并按 Enter，列表刷新且 Network 请求包含 `q`。
3. 选择标签或格式后，Network 请求包含 `tag` 或 `format`，已选择图片数量回到 0。
4. 修改排序字段和方向后，Network 请求包含 `sort` 和 `order`。
5. 搜索不存在的关键词后显示「没有匹配的图片」和「清空筛选」。
6. 清空筛选后恢复默认 `indexed_at desc` 列表。
7. 应用筛选后进入图片详情，再点击「返回图库」，筛选控件和值保持不变。
8. 设置页显示「识别 Provider」卡片，当前 Provider 为 `mock`，并提示 Phase 3 不支持页面切换。
9. 详情页「重新识别」和图库「批量识别」仍可完成请求并刷新结果。

- [ ] **步骤 5：在本计划追加验证记录**

在文件末尾追加：

```markdown
## 验证记录

- 后端完整测试：`cd backend && uv run pytest -q`，结果：全部测试通过，记录 pytest 输出中的 passed 数量。
- 前端生产构建：`cd frontend && npm run build`，结果：TypeScript 与 Vite build 通过。
- 后端 API 手动验证：`q`、`format`、非法 `sort`、非法 `order`、`/api/settings` 均符合预期。
- 前端手动验证：图库搜索、筛选、排序、空状态、返回保留筛选、Provider 卡片、单张识别和批量识别均符合预期。
```

提交验证记录：

```bash
git add docs/superpowers/plans/2026-05-29-picmind-phase-3.md
git commit -m "docs(PicMind): add phase three validation"
```

---

## 自检结果

- 规格覆盖度：本计划覆盖 `q` 搜索 caption/tags/file_path、标签筛选、格式筛选、排序字段和方向、非法 sort/order 400、分页保留、无结果返回空列表、图库工具栏、筛选变化清空选择、从详情返回保留筛选状态、设置页 Provider 卡片、Phase 2 单张识别和批量识别防回退验证。
- 范围边界：未新增标签聚合 API，标签和格式选项来自当前加载结果；未接入 Ollama 或云端模型；未实现 embedding、自然语言问答、批量任务持久化、取消、重试、多用户或同步。
- 占位符扫描：计划不包含空白占位、未定义类型、空泛错误处理或未展开的重复任务。
- 类型一致性：后端 query 参数为 `q/tag/format/sort/order`，前端 `ImageListParams` 使用同名字段；排序字段固定为 `indexed_at/modified_at/file_size/width/height`，排序方向固定为 `asc/desc`；错误文案与测试断言一致。

## 验证记录

- 后端完整测试：`cd "D:/my vibe coding/picture check/.claude/worktrees/picmind-phase-3/backend" && uv run pytest -q`，结果：52 passed。
- 前端生产构建：`cd "D:/my vibe coding/picture check/.claude/worktrees/picmind-phase-3/frontend" && npm run build`，结果：TypeScript 与 Vite build 通过，产物生成成功。
- 后端 API 手动验证：使用临时样例图片目录启动后端，`GET /api/images?q=...&sort=indexed_at&order=desc` 返回 200，`GET /api/images?format=PNG` 返回 2 条 PNG，非法 `sort=caption` 返回 400 `Unsupported sort field`，非法 `order=sideways` 返回 400 `Unsupported sort order`，`GET /api/settings` 返回 `provider: "mock"`。
- 识别流程验证：`POST /api/images/{image_id}/recognize` 返回 200 且 `model_used` 为 `mock`；`POST /api/recognition/batches` 返回 201 且状态为 `completed`；`GET /api/recognition/batches/{batch_id}` 返回同一进度。
- 前端运行验证：Vite dev server 返回 200 HTML；Playwright MCP Bridge 连接超时，未完成浏览器点击级验证。
