# PicMind 批次历史记录页面实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为 PicMind 增加独立“批次历史”页面，用户可查看历史批量识别任务、查看失败图片，并一键重新识别失败项。

**架构：** 后端复用现有 `RecognitionBatch` / `RecognitionBatchItem` / `Image` 表，新增只读分页查询 service 方法和两个 FastAPI GET 接口。前端新增 API client 类型与方法、独立 `BatchHistory` 页面，并在 `App` 顶部导航接入，不改变现有 Gallery active batch 工作流。

**技术栈：** FastAPI、SQLAlchemy、Pydantic、pytest、React、TypeScript、Vite、Tailwind CSS、源码守卫测试。

---

## 文件结构

- 修改：`backend/app/schemas.py`
  - 增加批次历史列表和批次 item 响应 schema。
  - 扩展 `RecognitionBatchResponse`，加入 `created_at`、`updated_at`，供历史列表展示。
- 修改：`backend/app/services/batch_recognition.py`
  - 增加 `list_batches(db, page, size)` 和 `list_batch_items(db, batch_id, page, size, status=None)`。
  - 查询只读，不启动识别，不修改批次状态。
- 修改：`backend/app/api/recognition.py`
  - 增加 `GET /api/recognition/batches`。
  - 增加 `GET /api/recognition/batches/{batch_id}/items`。
- 修改：`backend/tests/test_batch_recognition.py`
  - 增加 service 层分页、排序、状态筛选、404 行为测试。
- 修改：`backend/tests/test_api.py`
  - 增加 API 层列表、分页、item 响应、404、从失败项重新创建批次测试。
- 修改：`frontend/src/api/client.ts`
  - 增加 batch history 类型和 API 方法。
- 创建：`frontend/src/pages/BatchHistory.tsx`
  - 独立批次历史页面，左/上批次列表，右/下失败项详情。
- 修改：`frontend/src/App.tsx`
  - 增加 `batchHistory` 页面状态、导入页面、导航入口“批次历史”。
- 修改：`backend/tests/test_gallery_source.py`
  - 扩展为前端源码守卫，检查 BatchHistory 页面、API 方法、导航和 retry 行为。

---

### 任务 1：后端 schema 与 service 查询

**文件：**
- 修改：`backend/app/schemas.py`
- 修改：`backend/app/services/batch_recognition.py`
- 测试：`backend/tests/test_batch_recognition.py`

- [ ] **步骤 1：编写失败的 service 测试**

在 `backend/tests/test_batch_recognition.py` 文件末尾追加以下测试：

```python
def test_list_batches_returns_newest_first_with_pagination(db_session):
    for image_id in ["image-1", "image-2", "image-3"]:
        add_image(db_session, image_id)
    older = RecognitionBatch(
        id="batch-older",
        status="completed",
        total=1,
        created_at=datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
    )
    middle = RecognitionBatch(
        id="batch-middle",
        status="failed",
        total=1,
        created_at=datetime(2026, 6, 6, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 6, 12, 0, tzinfo=UTC),
    )
    newer = RecognitionBatch(
        id="batch-newer",
        status="running",
        total=1,
        created_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
    )
    older.items = [RecognitionBatchItem(image_id="image-1", status="completed")]
    middle.items = [RecognitionBatchItem(image_id="image-2", status="failed", error="boom")]
    newer.items = [RecognitionBatchItem(image_id="image-3", status="running")]
    db_session.add_all([older, middle, newer])
    db_session.commit()

    result = BatchRecognitionService().list_batches(db_session, page=1, size=2)

    assert result.total == 3
    assert result.page == 1
    assert result.size == 2
    assert [batch.batch_id for batch in result.items] == ["batch-newer", "batch-middle"]
    assert result.items[0].created_at == datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    assert result.items[0].updated_at == datetime(2026, 6, 7, 12, 0, tzinfo=UTC)


def test_list_batch_items_filters_failed_and_includes_image_details(db_session):
    add_image(db_session, "image-failed")
    add_image(db_session, "image-completed")
    batch = RecognitionBatch(id="batch-items", status="failed", total=2)
    batch.items = [
        RecognitionBatchItem(image_id="image-failed", status="failed", error="missing file"),
        RecognitionBatchItem(image_id="image-completed", status="completed"),
    ]
    db_session.add(batch)
    db_session.commit()

    result = BatchRecognitionService().list_batch_items(db_session, "batch-items", page=1, size=50, status="failed")

    assert result.total == 1
    assert result.page == 1
    assert result.size == 50
    assert len(result.items) == 1
    item = result.items[0]
    assert item.image_id == "image-failed"
    assert item.status == "failed"
    assert item.error == "missing file"
    assert item.image.id == "image-failed"
    assert item.image.file_path == "/tmp/image-failed.png"
    assert item.image.caption == ""
    assert item.image.image_url == "/api/images/image-failed/file"


def test_list_batch_items_raises_for_missing_batch(db_session):
    with pytest.raises(BatchNotFoundError, match="missing-batch"):
        BatchRecognitionService().list_batch_items(db_session, "missing-batch", page=1, size=50, status="failed")
```

- [ ] **步骤 2：运行 service 测试验证失败**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_batch_recognition.py::test_list_batches_returns_newest_first_with_pagination tests/test_batch_recognition.py::test_list_batch_items_filters_failed_and_includes_image_details tests/test_batch_recognition.py::test_list_batch_items_raises_for_missing_batch -q
```

预期：FAIL，包含 `AttributeError: 'BatchRecognitionService' object has no attribute 'list_batches'` 或 `list_batch_items`。

- [ ] **步骤 3：实现 schema**

在 `backend/app/schemas.py` 中，将现有 `RecognitionBatchResponse` 替换为：

```python
class RecognitionBatchResponse(BaseModel):
    batch_id: str
    total: int
    completed: int
    failed: int
    pending: int
    running: int
    cancelled: int = 0
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

在 `RecognitionBatchResponse` 后追加：

```python
class RecognitionBatchList(BaseModel):
    items: list[RecognitionBatchResponse]
    total: int
    page: int
    size: int


class RecognitionBatchItemImage(BaseModel):
    id: str
    file_path: str
    caption: str
    image_url: str


class RecognitionBatchItemResponse(BaseModel):
    id: int
    image_id: str
    status: str
    error: str | None
    image: RecognitionBatchItemImage


class RecognitionBatchItemList(BaseModel):
    items: list[RecognitionBatchItemResponse]
    total: int
    page: int
    size: int
```

- [ ] **步骤 4：实现 service 查询方法**

在 `backend/app/services/batch_recognition.py` 中，将 import 改为：

```python
from app.schemas import (
    RecognitionBatchItemImage,
    RecognitionBatchItemList,
    RecognitionBatchItemResponse,
    RecognitionBatchList,
    RecognitionBatchResponse,
)
```

将 `get_batch_progress()` 的 return 扩展为：

```python
return RecognitionBatchResponse(
    batch_id=batch.id,
    total=batch.total,
    completed=completed,
    failed=failed,
    pending=pending,
    running=running,
    cancelled=cancelled,
    status=batch.status,
    created_at=batch.created_at,
    updated_at=batch.updated_at,
)
```

在 `BatchRecognitionService` 中、`pause_batch()` 前加入：

```python
    def list_batches(self, db: Session, page: int, size: int) -> RecognitionBatchList:
        query = db.query(RecognitionBatch).order_by(RecognitionBatch.created_at.desc())
        total = query.count()
        batches = query.offset((page - 1) * size).limit(size).all()
        return RecognitionBatchList(
            items=[self.get_batch_progress(db, batch.id) for batch in batches],
            total=total,
            page=page,
            size=size,
        )

    def list_batch_items(
        self,
        db: Session,
        batch_id: str,
        page: int,
        size: int,
        status: str | None = None,
    ) -> RecognitionBatchItemList:
        self._get_batch_or_raise(db, batch_id)
        query = db.query(RecognitionBatchItem).filter(RecognitionBatchItem.batch_id == batch_id)
        if status:
            query = query.filter(RecognitionBatchItem.status == status)
        query = query.order_by(RecognitionBatchItem.id.asc())
        total = query.count()
        items = query.offset((page - 1) * size).limit(size).all()
        return RecognitionBatchItemList(
            items=[
                RecognitionBatchItemResponse(
                    id=item.id,
                    image_id=item.image_id,
                    status=item.status,
                    error=item.error,
                    image=RecognitionBatchItemImage(
                        id=item.image.id,
                        file_path=item.image.file_path,
                        caption=item.image.annotation.caption if item.image.annotation else "",
                        image_url=f"/api/images/{item.image.id}/file",
                    ),
                )
                for item in items
            ],
            total=total,
            page=page,
            size=size,
        )
```

- [ ] **步骤 5：运行 service 测试验证通过**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_batch_recognition.py::test_list_batches_returns_newest_first_with_pagination tests/test_batch_recognition.py::test_list_batch_items_filters_failed_and_includes_image_details tests/test_batch_recognition.py::test_list_batch_items_raises_for_missing_batch -q
```

预期：3 passed。

---

### 任务 2：后端批次历史 API

**文件：**
- 修改：`backend/app/api/recognition.py`
- 测试：`backend/tests/test_api.py`

- [ ] **步骤 1：编写失败的 API 测试**

在 `backend/tests/test_api.py` 中追加以下测试。若文件已有 `add_image` 或 client fixture 工具，复用现有工具；否则将测试中的 `db_session`、`client` fixture 名称调整为该文件现有名称。

```python
def test_get_recognition_batches_returns_history_newest_first(client, db_session):
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
    db_session.add_all([image_1, image_2, older, newer])
    db_session.commit()

    response = client.get("/api/recognition/batches?page=1&size=1")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["size"] == 1
    assert [item["batch_id"] for item in body["items"]] == ["api-batch-newer"]
    assert body["items"][0]["failed"] == 1
    assert body["items"][0]["created_at"].startswith("2026-06-07T12:00:00")


def test_get_recognition_batch_items_filters_failed_and_returns_image(client, db_session):
    now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    image = Image(
        id="failed-api-image",
        file_path="/tmp/failed-api-image.png",
        file_hash="failed-api-hash",
        file_size=100,
        width=32,
        height=24,
        format="PNG",
        created_at=now,
        modified_at=now,
        indexed_at=now,
    )
    annotation = Annotation(image_id="failed-api-image", caption="失败图片", tags=["红色"], objects=[], model_used="test")
    batch = RecognitionBatch(id="api-batch-items", status="failed", total=1)
    batch.items = [RecognitionBatchItem(image_id="failed-api-image", status="failed", error="missing file")]
    db_session.add_all([image, annotation, batch])
    db_session.commit()

    response = client.get("/api/recognition/batches/api-batch-items/items?page=1&size=50&status=failed")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["image_id"] == "failed-api-image"
    assert body["items"][0]["status"] == "failed"
    assert body["items"][0]["error"] == "missing file"
    assert body["items"][0]["image"] == {
        "id": "failed-api-image",
        "file_path": "/tmp/failed-api-image.png",
        "caption": "失败图片",
        "image_url": "/api/images/failed-api-image/file",
    }


def test_get_recognition_batch_items_returns_404_for_missing_batch(client):
    response = client.get("/api/recognition/batches/missing-batch/items?status=failed")

    assert response.status_code == 404
    assert response.json()["detail"] == "Batch not found"


def test_failed_batch_items_can_create_new_recognition_batch(client, db_session):
    now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    image = Image(
        id="retry-api-image",
        file_path="/tmp/retry-api-image.png",
        file_hash="retry-api-hash",
        file_size=100,
        width=32,
        height=24,
        format="PNG",
        created_at=now,
        modified_at=now,
        indexed_at=now,
    )
    batch = RecognitionBatch(id="api-retry-source", status="failed", total=1)
    batch.items = [RecognitionBatchItem(image_id="retry-api-image", status="failed", error="boom")]
    db_session.add_all([image, batch])
    db_session.commit()

    items_response = client.get("/api/recognition/batches/api-retry-source/items?status=failed")
    image_ids = [item["image_id"] for item in items_response.json()["items"]]
    create_response = client.post("/api/recognition/batches", json={"image_ids": image_ids})

    assert create_response.status_code == 202
    body = create_response.json()
    assert body["total"] == 1
    assert body["pending"] == 1
    assert body["status"] == "queued"
```

同时确保 `backend/tests/test_api.py` 顶部有这些 import；如果已有则不要重复：

```python
from datetime import UTC, datetime

from app.models import Annotation, Image, RecognitionBatch, RecognitionBatchItem
```

- [ ] **步骤 2：运行 API 测试验证失败**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_api.py::test_get_recognition_batches_returns_history_newest_first tests/test_api.py::test_get_recognition_batch_items_filters_failed_and_returns_image tests/test_api.py::test_get_recognition_batch_items_returns_404_for_missing_batch tests/test_api.py::test_failed_batch_items_can_create_new_recognition_batch -q
```

预期：FAIL，至少第一个接口返回 405/404，因为 GET list/items endpoints 尚不存在。

- [ ] **步骤 3：实现 API endpoints**

在 `backend/app/api/recognition.py` import 中，将 schema import 改为：

```python
from app.schemas import (
    ImageDetail,
    RecognitionBatchCreate,
    RecognitionBatchItemList,
    RecognitionBatchList,
    RecognitionBatchResponse,
)
```

在 `create_recognition_batch()` 和 `get_recognition_batch()` 之间加入：

```python
@router.get("/api/recognition/batches", response_model=RecognitionBatchList)
def list_recognition_batches(
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
    batch_service: BatchRecognitionService = Depends(get_batch_recognition_service),
) -> RecognitionBatchList:
    return batch_service.list_batches(db, page, size)


@router.get("/api/recognition/batches/{batch_id}/items", response_model=RecognitionBatchItemList)
def list_recognition_batch_items(
    batch_id: str,
    page: int = 1,
    size: int = 50,
    status: str | None = None,
    db: Session = Depends(get_db),
    batch_service: BatchRecognitionService = Depends(get_batch_recognition_service),
) -> RecognitionBatchItemList:
    try:
        return batch_service.list_batch_items(db, batch_id, page, size, status)
    except BatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Batch not found") from exc
```

- [ ] **步骤 4：运行 API 测试验证通过**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_api.py::test_get_recognition_batches_returns_history_newest_first tests/test_api.py::test_get_recognition_batch_items_filters_failed_and_returns_image tests/test_api.py::test_get_recognition_batch_items_returns_404_for_missing_batch tests/test_api.py::test_failed_batch_items_can_create_new_recognition_batch -q
```

预期：4 passed。

---

### 任务 3：前端 API client

**文件：**
- 修改：`frontend/src/api/client.ts`
- 测试：`backend/tests/test_gallery_source.py`

- [ ] **步骤 1：编写失败的源码守卫**

在 `backend/tests/test_gallery_source.py` 顶部常量后加入：

```python
API_CLIENT_SOURCE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "client.ts"
```

在文件末尾追加：

```python
def test_api_client_supports_batch_history_endpoints():
    source = API_CLIENT_SOURCE.read_text(encoding="utf-8")

    assert "export type RecognitionBatchList" in source
    assert "export type RecognitionBatchItemImage" in source
    assert "export type RecognitionBatchItem" in source
    assert "export type RecognitionBatchItemList" in source
    assert "created_at?: string" in source
    assert "updated_at?: string" in source
    assert "listRecognitionBatches" in source
    assert "listRecognitionBatchItems" in source
    assert "status=failed" not in source
    assert "searchParams.set('status', params.status)" in source
```

- [ ] **步骤 2：运行源码守卫验证失败**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_gallery_source.py::test_api_client_supports_batch_history_endpoints -q
```

预期：FAIL，包含 `AssertionError`，因为 API client 尚未新增类型/方法。

- [ ] **步骤 3：实现 API client 类型和方法**

在 `frontend/src/api/client.ts` 中，将 `RecognitionBatch` 类型替换为：

```ts
export type RecognitionBatch = {
  batch_id: string;
  total: number;
  completed: number;
  failed: number;
  pending: number;
  running: number;
  cancelled: number;
  status: string;
  created_at?: string;
  updated_at?: string;
};

export type RecognitionBatchList = {
  items: RecognitionBatch[];
  total: number;
  page: number;
  size: number;
};

export type RecognitionBatchItemImage = {
  id: string;
  file_path: string;
  caption: string;
  image_url: string;
};

export type RecognitionBatchItem = {
  id: number;
  image_id: string;
  status: string;
  error: string | null;
  image: RecognitionBatchItemImage;
};

export type RecognitionBatchItemList = {
  items: RecognitionBatchItem[];
  total: number;
  page: number;
  size: number;
};

export type RecognitionBatchListParams = {
  page?: number;
  size?: number;
};

export type RecognitionBatchItemListParams = {
  page?: number;
  size?: number;
  status?: string;
};
```

在 `api` 对象中、`getRecognitionBatch` 前加入：

```ts
  listRecognitionBatches: (params: RecognitionBatchListParams = {}) => {
    const searchParams = new URLSearchParams({
      page: String(params.page ?? 1),
      size: String(params.size ?? 20),
    });
    return request<RecognitionBatchList>(`/api/recognition/batches?${searchParams}`);
  },
  listRecognitionBatchItems: (batchId: string, params: RecognitionBatchItemListParams = {}) => {
    const searchParams = new URLSearchParams({
      page: String(params.page ?? 1),
      size: String(params.size ?? 50),
    });
    if (params.status) searchParams.set('status', params.status);
    return request<RecognitionBatchItemList>(
      `/api/recognition/batches/${encodeURIComponent(batchId)}/items?${searchParams}`,
    );
  },
```

- [ ] **步骤 4：运行源码守卫验证通过**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_gallery_source.py::test_api_client_supports_batch_history_endpoints -q
```

预期：1 passed。

---

### 任务 4：BatchHistory 页面源码与导航守卫

**文件：**
- 创建：`frontend/src/pages/BatchHistory.tsx`
- 修改：`frontend/src/App.tsx`
- 修改：`backend/tests/test_gallery_source.py`

- [ ] **步骤 1：编写失败的 BatchHistory 源码守卫**

在 `backend/tests/test_gallery_source.py` 顶部常量后加入：

```python
APP_SOURCE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "App.tsx"
BATCH_HISTORY_SOURCE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "BatchHistory.tsx"
```

在文件末尾追加：

```python
def test_batch_history_page_source_contains_required_behaviors():
    source = BATCH_HISTORY_SOURCE.read_text(encoding="utf-8")

    assert "批次历史" in source
    assert "api.listRecognitionBatches" in source
    assert "api.listRecognitionBatchItems" in source
    assert "status: 'failed'" in source
    assert "重新识别失败项" in source
    assert "api.createRecognitionBatch" in source
    assert "已创建新的识别批次" in source
    assert "这个批次没有失败图片" in source
    assert "failedItems.items.map" in source
    assert "item.image.image_url" in source
    assert "item.image.file_path" in source
    assert "item.error" in source


def test_app_navigation_includes_batch_history_page():
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "import BatchHistory from './pages/BatchHistory'" in source
    assert "batchHistory" in source
    assert "批次历史" in source
    assert "<BatchHistory />" in source
```

- [ ] **步骤 2：运行源码守卫验证失败**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_gallery_source.py::test_batch_history_page_source_contains_required_behaviors tests/test_gallery_source.py::test_app_navigation_includes_batch_history_page -q
```

预期：FAIL，`BatchHistory.tsx` 文件不存在或导航未包含 `BatchHistory`。

- [ ] **步骤 3：创建 BatchHistory 页面**

创建 `frontend/src/pages/BatchHistory.tsx`，内容如下：

```tsx
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, type RecognitionBatch, type RecognitionBatchItemList } from '../api/client';

const batchPageSize = 20;
const itemPageSize = 50;

const statusClassName = (status: string) => {
  if (status === 'queued' || status === 'running') return 'bg-blue-100 text-blue-700';
  if (status === 'paused') return 'bg-yellow-100 text-yellow-700';
  if (status === 'completed') return 'bg-green-100 text-green-700';
  if (status === 'failed') return 'bg-red-100 text-red-700';
  if (status === 'cancelled') return 'bg-slate-200 text-slate-600';
  return 'bg-slate-100 text-slate-700';
};

const formatDateTime = (value?: string) => (value ? new Date(value).toLocaleString() : '-');

export default function BatchHistory() {
  const [batches, setBatches] = useState<RecognitionBatch[]>([]);
  const [batchTotal, setBatchTotal] = useState(0);
  const [batchPage, setBatchPage] = useState(1);
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [failedItems, setFailedItems] = useState<RecognitionBatchItemList | null>(null);
  const [loadingBatches, setLoadingBatches] = useState(false);
  const [loadingItems, setLoadingItems] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const batchPageCount = useMemo(() => Math.max(1, Math.ceil(batchTotal / batchPageSize)), [batchTotal]);

  const loadBatches = useCallback((page: number) => {
    setLoadingBatches(true);
    setError(null);
    api
      .listRecognitionBatches({ page, size: batchPageSize })
      .then((data) => {
        setBatches(data.items);
        setBatchTotal(data.total);
        setBatchPage(data.page);
        setSelectedBatchId((current) => current ?? data.items[0]?.batch_id ?? null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoadingBatches(false));
  }, []);

  const loadFailedItems = useCallback((batchId: string) => {
    setLoadingItems(true);
    setError(null);
    api
      .listRecognitionBatchItems(batchId, { page: 1, size: itemPageSize, status: 'failed' })
      .then(setFailedItems)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoadingItems(false));
  }, []);

  useEffect(() => {
    loadBatches(1);
  }, [loadBatches]);

  useEffect(() => {
    if (!selectedBatchId) {
      setFailedItems(null);
      return;
    }
    loadFailedItems(selectedBatchId);
  }, [loadFailedItems, selectedBatchId]);

  const retryFailedItems = async () => {
    if (!failedItems || failedItems.items.length === 0) return;
    setRetrying(true);
    setError(null);
    setMessage(null);
    try {
      await api.createRecognitionBatch(failedItems.items.map((item) => item.image_id));
      setMessage('已创建新的识别批次');
    } catch (err) {
      setError(err instanceof Error ? err.message : '重新识别失败项失败');
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">批次历史</h2>
        <p className="text-sm text-slate-500">查看过去的批量识别任务和失败图片</p>
      </div>

      {error && <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {message && <div className="rounded-lg bg-green-50 px-4 py-3 text-sm text-green-700">{message}</div>}

      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <section className="rounded-xl border bg-white p-4 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-semibold">历史批次</h3>
            <span className="text-sm text-slate-500">共 {batchTotal} 个</span>
          </div>
          {loadingBatches && <p className="text-sm text-slate-500">加载中...</p>}
          <div className="space-y-3">
            {batches.map((batch) => (
              <button
                key={batch.batch_id}
                onClick={() => setSelectedBatchId(batch.batch_id)}
                className={`w-full rounded-lg border p-3 text-left text-sm ${selectedBatchId === batch.batch_id ? 'border-slate-900 bg-slate-50' : 'border-slate-200 hover:bg-slate-50'}`}
              >
                <div className="mb-2 flex items-center justify-between">
                  <span className={`rounded-full px-2 py-1 text-xs ${statusClassName(batch.status)}`}>{batch.status}</span>
                  <span className="text-xs text-slate-500">{batch.batch_id.slice(0, 8)}</span>
                </div>
                <div className="grid grid-cols-2 gap-1 text-xs text-slate-600">
                  <span>总数 {batch.total}</span>
                  <span>完成 {batch.completed}</span>
                  <span>失败 {batch.failed}</span>
                  <span>待处理 {batch.pending}</span>
                  <span>运行 {batch.running}</span>
                  <span>取消 {batch.cancelled}</span>
                </div>
                <div className="mt-2 space-y-1 text-xs text-slate-500">
                  <p>创建：{formatDateTime(batch.created_at)}</p>
                  <p>更新：{formatDateTime(batch.updated_at)}</p>
                </div>
              </button>
            ))}
          </div>
          <div className="mt-4 flex items-center justify-between text-sm">
            <button
              onClick={() => loadBatches(batchPage - 1)}
              disabled={batchPage <= 1 || loadingBatches}
              className="rounded-lg bg-slate-100 px-3 py-2 disabled:opacity-50"
            >
              上一页
            </button>
            <span className="text-slate-500">{batchPage} / {batchPageCount}</span>
            <button
              onClick={() => loadBatches(batchPage + 1)}
              disabled={batchPage >= batchPageCount || loadingBatches}
              className="rounded-lg bg-slate-100 px-3 py-2 disabled:opacity-50"
            >
              下一页
            </button>
          </div>
        </section>

        <section className="rounded-xl border bg-white p-4 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-semibold">失败图片</h3>
              <p className="text-sm text-slate-500">默认只显示 status=failed 的批次 item</p>
            </div>
            {failedItems && failedItems.items.length > 0 && (
              <button
                onClick={retryFailedItems}
                disabled={retrying}
                className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
              >
                {retrying ? '创建中...' : '重新识别失败项'}
              </button>
            )}
          </div>

          {!selectedBatchId && <p className="text-sm text-slate-500">请选择一个批次</p>}
          {selectedBatchId && loadingItems && <p className="text-sm text-slate-500">加载失败项中...</p>}
          {selectedBatchId && !loadingItems && failedItems?.items.length === 0 && (
            <p className="text-sm text-slate-500">这个批次没有失败图片</p>
          )}
          <div className="grid gap-4 md:grid-cols-2">
            {failedItems?.items.map((item) => (
              <article key={item.id} className="overflow-hidden rounded-lg border border-slate-200">
                <img src={item.image.image_url} alt={item.image.file_path} className="h-40 w-full object-cover" />
                <div className="space-y-2 p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className={`rounded-full px-2 py-1 text-xs ${statusClassName(item.status)}`}>{item.status}</span>
                    <span className="text-xs text-slate-500">{item.image_id.slice(0, 8)}</span>
                  </div>
                  <p className="break-all text-slate-700">{item.image.file_path}</p>
                  <p className="text-slate-500">{item.error || '无错误信息'}</p>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
```

- [ ] **步骤 4：接入 App 导航**

在 `frontend/src/App.tsx` 中加入 import：

```ts
import BatchHistory from './pages/BatchHistory';
```

将 Page 类型改为：

```ts
type Page = 'gallery' | 'dashboard' | 'settings' | 'batchHistory';
```

将 nav 数组改为：

```tsx
{(['gallery', 'dashboard', 'settings', 'batchHistory'] as Page[]).map((item) => (
```

将按钮文案表达式改为：

```tsx
{item === 'gallery' ? '图库' : item === 'dashboard' ? '看板' : item === 'settings' ? '设置' : '批次历史'}
```

在 main 中追加页面渲染：

```tsx
{page === 'batchHistory' && <BatchHistory />}
```

- [ ] **步骤 5：运行源码守卫验证通过**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_gallery_source.py::test_batch_history_page_source_contains_required_behaviors tests/test_gallery_source.py::test_app_navigation_includes_batch_history_page -q
```

预期：2 passed。

---

### 任务 5：完整自动化验证与浏览器手动验证

**文件：**
- 不新增文件。
- 可能修改：前面任务中发现的测试或类型错误对应文件。

- [ ] **步骤 1：运行后端完整测试**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest -q
```

预期：全部 passed。若失败，读取失败信息，只修复与本批次历史实现直接相关的问题。

- [ ] **步骤 2：运行前端构建**

运行：

```bash
npm --prefix "D:/my vibe coding/picture check/frontend" run build
```

预期：exit 0，TypeScript/Vite build 成功。

- [ ] **步骤 3：启动应用并手动验证 UI**

启动后端和前端，使用项目当前的启动方式。如果没有现成脚本，使用：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run uvicorn app.main:app --reload
npm --prefix "D:/my vibe coding/picture check/frontend" run dev
```

浏览器验证：

1. 打开前端本地地址。
2. 点击顶部“批次历史”。
3. 确认历史批次列表按创建时间倒序显示。
4. 点击一个失败批次。
5. 确认详情默认显示失败图片。
6. 确认失败图片包含缩略图、路径、状态、错误原因。
7. 点击“重新识别失败项”。
8. 确认页面显示“已创建新的识别批次”。
9. 确认不会自动跳转 Gallery。
10. 窄屏检查：页面上下排列且可操作。

- [ ] **步骤 4：最终 git 检查**

运行：

```bash
git status --short
```

预期：只包含本计划范围内文件：

```text
M backend/app/schemas.py
M backend/app/services/batch_recognition.py
M backend/app/api/recognition.py
M backend/tests/test_batch_recognition.py
M backend/tests/test_api.py
M backend/tests/test_gallery_source.py
M frontend/src/api/client.ts
M frontend/src/App.tsx
?? frontend/src/pages/BatchHistory.tsx
```

不要在未获得用户明确确认前提交代码。

---

## 自检

- 规格覆盖：
  - 独立页面：任务 4。
  - 顶部导航入口：任务 4。
  - 批次列表倒序和分页：任务 1、2、4。
  - 批次详情默认失败项：任务 1、2、4。
  - failed 状态筛选：任务 1、2、3、4。
  - 缩略图、路径、状态、错误原因：任务 1、2、4。
  - 重新识别失败项：任务 2、4。
  - 后端 schema/service/API/tests：任务 1、2。
  - 前端 API/page/navigation/source guards：任务 3、4。
  - 完整验证：任务 5。
- 占位符扫描：未发现未完成标记、延后实现标记或未定义的计划步骤。
- 类型一致性：
  - 后端 list 响应使用 `RecognitionBatchList` / `RecognitionBatchItemList`。
  - 前端 list 方法使用 `RecognitionBatchListParams` / `RecognitionBatchItemListParams`。
  - 页面使用 `RecognitionBatch` / `RecognitionBatchItemList`。
- 用户约束：此计划只创建实现计划；执行计划时不要在未确认前提交代码。
