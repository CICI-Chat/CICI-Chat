# PicMind YOLO11n 物体识别实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional YOLO11n object detection provider to PicMind's recognition pipeline, writing detected objects to `Annotation.objects` and `Annotation.tags`.

**Architecture:** New file `backend/app/services/yolo_recognizer.py` implements the existing `Recognizer` protocol, wrapping `ultralytics.YOLO`. A `build_recognizer()` factory selects between `MockRecognizer` and `YoloRecognizer` based on `RECOGNITION_PROVIDER` env var. Frontend receives `recognition_provider` from `/api/settings` and displays detected objects in image detail page.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Ultralytics YOLO11n, PyTorch, pytest, React/Vite/TypeScript, Vitest.

---

## 文件结构

- 创建：`backend/app/services/yolo_label_map.py` — COCO 80 类英文→中文静态映射。
- 创建：`backend/app/services/yolo_recognizer.py` — 实现 `Recognizer` 协议，懒加载 YOLO11n 模型并执行 CPU 推理。
- 修改：`backend/app/config.py` — 新增 `recognition_provider`、`yolo_model_path`、`yolo_confidence_threshold`。
- 修改：`backend/app/services/recognition.py` — 新增 `build_recognizer(settings) -> Recognizer` 工厂函数。
- 修改：`backend/app/api/recognition.py` — 模块级 `recognition_service` 改用 `build_recognizer` 构造。
- 修改：`backend/app/main.py` — 创建 `BatchRecognitionService` 时注入 `build_recognizer` 构造的 RecognitionService。
- 修改：`backend/app/api/settings.py` — `get_app_settings` 改为从 settings 取真实 provider。
- 修改：`backend/pyproject.toml` — 追加 `ultralytics>=8.3,<9.0` 到 `dependencies`。
- 创建：`backend/tests/test_yolo_label_map.py` — 中文名映射和 fallback。
- 创建：`backend/tests/test_yolo_recognizer.py` — 阈值过滤、排序、去重、模型不存在异常（用 monkeypatch 替换模型加载）。
- 创建：`backend/tests/test_recognizer_factory.py` — `build_recognizer` 在 mock / yolo 下的不同路径。
- 修改：`backend/tests/test_api.py` — `/api/settings` 返回 provider 字段的集成测试。
- 修改：`frontend/src/pages/Settings.tsx` — 展示动态 provider 文案（Phase 2）。
- 修改：`frontend/src/pages/ImageDetail.tsx` — 检测到物体的列表（Phase 2）。
- 创建：`docs/CODEMAPS/yolo-integration-verification.md` — Phase 3 手工验证清单。

---

## 任务 1：COCO 中文标签映射表

**文件：**
- 创建：`backend/app/services/yolo_label_map.py`
- 测试：`backend/tests/test_yolo_label_map.py`

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_yolo_label_map.py`：

```python
from app.services.yolo_label_map import COCO_LABEL_TO_CHINESE_NAME, chinese_name_for_label


def test_chinese_name_for_label_known():
    assert chinese_name_for_label("person") == "人"
    assert chinese_name_for_label("car") == "汽车"
    assert chinese_name_for_label("dog") == "狗"


def test_chinese_name_for_label_unknown_fallback():
    assert chinese_name_for_label("nonexistent_label") == "nonexistent_label"


def test_coco_label_count():
    assert len(COCO_LABEL_TO_CHINESE_NAME) == 80
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_yolo_label_map.py -q
```

预期：FAIL，报错 `ModuleNotFoundError: No module named 'app.services.yolo_label_map'`

- [ ] **步骤 3：编写最少实现代码**

创建 `backend/app/services/yolo_label_map.py`：

```python
COCO_LABEL_TO_CHINESE_NAME: dict[str, str] = {
    "person": "人",
    "bicycle": "自行车",
    "car": "汽车",
    "motorcycle": "摩托车",
    "airplane": "飞机",
    "bus": "公交车",
    "train": "火车",
    "truck": "卡车",
    "boat": "船",
    "traffic light": "红绿灯",
    "fire hydrant": "消防栓",
    "stop sign": "停止标志",
    "parking meter": "停车计时器",
    "bench": "长椅",
    "bird": "鸟",
    "cat": "猫",
    "dog": "狗",
    "horse": "马",
    "sheep": "羊",
    "cow": "牛",
    "elephant": "大象",
    "bear": "熊",
    "zebra": "斑马",
    "giraffe": "长颈鹿",
    "backpack": "背包",
    "umbrella": "雨伞",
    "handbag": "手提包",
    "tie": "领带",
    "suitcase": "行李箱",
    "frisbee": "飞盘",
    "skis": "滑雪板",
    "snowboard": "单板滑雪板",
    "sports ball": "运动球",
    "kite": "风筝",
    "baseball bat": "棒球棒",
    "baseball glove": "棒球手套",
    "skateboard": "滑板",
    "surfboard": "冲浪板",
    "tennis racket": "网球拍",
    "bottle": "瓶子",
    "wine glass": "酒杯",
    "cup": "杯子",
    "fork": "叉子",
    "knife": "刀",
    "spoon": "勺子",
    "bowl": "碗",
    "banana": "香蕉",
    "apple": "苹果",
    "sandwich": "三明治",
    "orange": "橙子",
    "broccoli": "西兰花",
    "carrot": "胡萝卜",
    "hot dog": "热狗",
    "pizza": "披萨",
    "donut": "甜甜圈",
    "cake": "蛋糕",
    "chair": "椅子",
    "couch": "沙发",
    "potted plant": "盆栽",
    "bed": "床",
    "dining table": "餐桌",
    "toilet": "马桶",
    "tv": "电视",
    "laptop": "笔记本电脑",
    "mouse": "鼠标",
    "remote": "遥控器",
    "keyboard": "键盘",
    "cell phone": "手机",
    "microwave": "微波炉",
    "oven": "烤箱",
    "toaster": "烤面包机",
    "sink": "水槽",
    "refrigerator": "冰箱",
    "book": "书",
    "clock": "时钟",
    "vase": "花瓶",
    "scissors": "剪刀",
    "teddy bear": "泰迪熊",
    "hair drier": "吹风机",
    "toothbrush": "牙刷",
}


def chinese_name_for_label(label: str) -> str:
    return COCO_LABEL_TO_CHINESE_NAME.get(label, label)
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd backend && uv run pytest tests/test_yolo_label_map.py -q
```

预期：PASS（3 项）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/yolo_label_map.py backend/tests/test_yolo_label_map.py
git commit -m "feat(PicMind): add COCO 80-class Chinese label map"
```

---

## 任务 2：YoloRecognizer 实现

**文件：**
- 创建：`backend/app/services/yolo_recognizer.py`
- 测试：`backend/tests/test_yolo_recognizer.py`
- 修改：`backend/pyproject.toml`

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_yolo_recognizer.py`：

```python
from pathlib import Path

import pytest
from PIL import Image as PillowImage

from app.services.annotation import ImageRecognitionInput
from app.services.yolo_recognizer import (
    YoloModelMissingError,
    YoloRecognizer,
)


def _make_image_input(file_path: Path, width: int = 640, height: int = 480) -> ImageRecognitionInput:
    return ImageRecognitionInput(
        image_id="test-id",
        file_path=str(file_path),
        width=width,
        height=height,
        format="jpg",
    )


def test_yolo_recognizer_raises_when_model_missing(tmp_path):
    img_path = tmp_path / "img.jpg"
    PillowImage.new("RGB", (10, 10), color=(255, 0, 0)).save(img_path)

    recognizer = YoloRecognizer(model_path="/definitely/not/here.pt", confidence_threshold=0.25)
    with pytest.raises(YoloModelMissingError):
        recognizer.recognize(_make_image_input(img_path))


def test_yolo_recognizer_filters_low_confidence_and_sorts(monkeypatch, tmp_path):
    """fake 模型返回 3 个检测，1 个低于阈值；验证排序和阈值过滤。"""
    img_path = tmp_path / "img.jpg"
    PillowImage.new("RGB", (640, 480), color=(255, 0, 0)).save(img_path)
    model_file = tmp_path / "yolo11n.pt"
    model_file.write_bytes(b"fake model")

    recognizer = YoloRecognizer(model_path=str(model_file), confidence_threshold=0.25)

    class FakeBox:
        def __init__(self, cls_idx: int, conf: float) -> None:
            class _T:
                def __init__(self, v): self._v = v
                def item(self): return self._v
            self.cls = [_T(cls_idx)]
            self.conf = [_T(conf)]

    class FakeResult:
        names = {0: "person", 1: "car", 2: "dog"}
        boxes = [FakeBox(0, 0.91), FakeBox(1, 0.84), FakeBox(2, 0.12)]

    def fake_call(_path, **_kwargs):
        return [FakeResult()]

    def fake_load(self):
        self._model = type("FakeModel", (), {"__call__": staticmethod(fake_call)})()

    monkeypatch.setattr(YoloRecognizer, "_load_model", fake_load)

    result = recognizer.recognize(_make_image_input(img_path))

    assert result.model_used == "yolo11n"
    assert result.caption == "本地图片"
    assert len(result.objects) == 2
    assert result.objects[0]["label"] == "person"
    assert result.objects[0]["name"] == "人"
    assert result.objects[1]["label"] == "car"
    assert result.objects[1]["name"] == "汽车"
    assert "人" in result.tags
    assert "汽车" in result.tags
    assert "狗" not in result.tags
    assert "本地图片" in result.tags
    assert "landscape" in result.tags


def test_yolo_recognizer_dedupes_repeated_labels(monkeypatch, tmp_path):
    img_path = tmp_path / "img.jpg"
    PillowImage.new("RGB", (640, 480), color=(0, 0, 255)).save(img_path)
    model_file = tmp_path / "yolo11n.pt"
    model_file.write_bytes(b"fake")

    recognizer = YoloRecognizer(model_path=str(model_file), confidence_threshold=0.25)

    class FakeBox:
        def __init__(self, cls_idx: int, conf: float) -> None:
            class _T:
                def __init__(self, v): self._v = v
                def item(self): return self._v
            self.cls = [_T(cls_idx)]
            self.conf = [_T(conf)]

    class FakeResult:
        names = {0: "person"}
        boxes = [FakeBox(0, 0.91), FakeBox(0, 0.88), FakeBox(0, 0.55)]

    def fake_call(_path, **_kwargs):
        return [FakeResult()]

    def fake_load(self):
        self._model = type("FakeModel", (), {"__call__": staticmethod(fake_call)})()

    monkeypatch.setattr(YoloRecognizer, "_load_model", fake_load)

    result = recognizer.recognize(_make_image_input(img_path))

    person_tag_count = sum(1 for t in result.tags if t == "人")
    assert person_tag_count == 1
    assert len(result.objects) == 3
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd backend && uv run pytest tests/test_yolo_recognizer.py -q
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.yolo_recognizer'`

- [ ] **步骤 3：追加 ultralytics 依赖**

```bash
cd backend && uv add "ultralytics>=8.3,<9.0"
```

注意：这会传递安装 `torch` 和 `torchvision`，体积较大。

- [ ] **步骤 4：编写最少实现代码**

创建 `backend/app/services/yolo_recognizer.py`：

```python
from pathlib import Path
from threading import Lock

from app.services.annotation import (
    ImageRecognitionInput,
    Recognizer,
    RecognitionResult,
)
from app.services.color_analysis import detect_dominant_color_label
from app.services.yolo_label_map import chinese_name_for_label


class YoloModelMissingError(Exception):
    """Raised when the configured YOLO model file does not exist."""


class YoloRuntimeError(Exception):
    """Raised when YOLO inference fails."""


class YoloRecognizer(Recognizer):
    def __init__(self, model_path: str | Path, confidence_threshold: float = 0.25) -> None:
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._lock = Lock()

    def _load_model(self) -> None:
        if not self.model_path.exists():
            raise YoloModelMissingError(
                f"YOLO model not found: {self.model_path}. "
                f"Set YOLO_MODEL_PATH in .env or switch RECOGNITION_PROVIDER back to mock."
            )
        from ultralytics import YOLO  # local import keeps optional dep off the hot path
        self._model = YOLO(str(self.model_path))

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is None:
                self._load_model()

    def recognize(self, image: ImageRecognitionInput) -> RecognitionResult:
        self._ensure_model()

        file_path = Path(image.file_path)
        try:
            results = self._model(str(file_path), verbose=False)
        except YoloModelMissingError:
            raise
        except Exception as exc:
            raise YoloRuntimeError(f"YOLO inference failed for {file_path}: {exc}") from exc

        tags_set: set[str] = {"本地图片"}
        if image.width > image.height:
            tags_set.add("landscape")
        elif image.height > image.width:
            tags_set.add("portrait")
        else:
            tags_set.add("square")

        if file_path.exists() and file_path.is_file():
            color_label = detect_dominant_color_label(file_path)
            if color_label is not None:
                tags_set.add(color_label)

        objects: list[dict] = []
        for result in results:
            boxes = getattr(result, "boxes", None)
            if not boxes:
                continue
            names = getattr(result, "names", {})
            for box in boxes:
                label_idx = int(box.cls[0].item())
                label = names.get(label_idx, str(label_idx))
                confidence = round(float(box.conf[0].item()), 4)
                if confidence < self.confidence_threshold:
                    continue
                name = chinese_name_for_label(label)
                tags_set.add(name)
                objects.append({
                    "label": label,
                    "name": name,
                    "confidence": confidence,
                })

        objects.sort(key=lambda obj: obj["confidence"], reverse=True)
        objects = objects[:20]

        return RecognitionResult(
            caption="本地图片",
            tags=sorted(tags_set),
            objects=objects,
            model_used="yolo11n",
        )
```

- [ ] **步骤 5：运行测试验证通过**

```bash
cd backend && uv run pytest tests/test_yolo_recognizer.py -q
```

预期：PASS（3 项）

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/yolo_recognizer.py backend/tests/test_yolo_recognizer.py backend/pyproject.toml backend/uv.lock
git commit -m "feat(PicMind): add YOLO11n recognizer with confidence threshold"
```

---

## 任务 3：配置项与 build_recognizer 工厂

**文件：**
- 修改：`backend/app/config.py`
- 修改：`backend/app/services/recognition.py`
- 测试：`backend/tests/test_recognizer_factory.py`

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_recognizer_factory.py`：

```python
from pathlib import Path

import pytest

from app.config import Settings
from app.services.annotation import MockRecognizer
from app.services.recognition import build_recognizer
from app.services.yolo_recognizer import YoloModelMissingError, YoloRecognizer


def test_build_recognizer_returns_mock_by_default():
    settings = Settings(recognition_provider="mock")
    recognizer = build_recognizer(settings)
    assert isinstance(recognizer, MockRecognizer)


def test_build_recognizer_yolo_with_missing_model_raises():
    settings = Settings(
        recognition_provider="yolo",
        yolo_model_path=Path("/definitely/missing/model.pt"),
        yolo_confidence_threshold=0.25,
    )
    with pytest.raises(YoloModelMissingError):
        build_recognizer(settings)


def test_build_recognizer_yolo_with_existing_model_returns_yolo(monkeypatch, tmp_path):
    model_file = tmp_path / "yolo11n.pt"
    model_file.write_bytes(b"fake model bytes")

    settings = Settings(
        recognition_provider="yolo",
        yolo_model_path=model_file,
        yolo_confidence_threshold=0.3,
    )

    recognizer = build_recognizer(settings)
    assert isinstance(recognizer, YoloRecognizer)
    assert recognizer.model_path == model_file
    assert recognizer.confidence_threshold == 0.3
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd backend && uv run pytest tests/test_recognizer_factory.py -q
```

预期：FAIL（`build_recognizer` 不存在，`Settings` 缺字段）。

- [ ] **步骤 3：在 `config.py` 追加配置项**

修改 `backend/app/config.py`，在 `Settings` 类内 `db_path` 字段之后追加：

```python
    recognition_provider: str = Field(default="mock", alias="RECOGNITION_PROVIDER")
    yolo_model_path: Path = Field(
        default=Path("D:/my vibe coding/models/yolo/yolo11n.pt"),
        alias="YOLO_MODEL_PATH",
    )
    yolo_confidence_threshold: float = Field(default=0.25, alias="YOLO_CONFIDENCE_THRESHOLD")
```

- [ ] **步骤 4：在 `recognition.py` 追加 `build_recognizer`**

修改 `backend/app/services/recognition.py`，在 import 区域追加：

```python
from app.config import Settings as PicMindSettings
```

在 `RecognitionService` 类定义之前追加：

```python
def build_recognizer(settings: PicMindSettings) -> Recognizer:
    if settings.recognition_provider == "yolo":
        try:
            from app.services.yolo_recognizer import YoloRecognizer
        except ImportError as exc:
            raise ImportError(
                "ultralytics is not installed. "
                "Run `uv add ultralytics` in backend/ or switch RECOGNITION_PROVIDER back to mock."
            ) from exc
        recognizer = YoloRecognizer(
            model_path=settings.yolo_model_path,
            confidence_threshold=settings.yolo_confidence_threshold,
        )
        recognizer._ensure_model()
        return recognizer
    return MockRecognizer()
```

注意：在 factory 中调用 `_ensure_model()` 是为了让模型缺失能在应用启动期就抛出 `YoloModelMissingError`，而不是延迟到第一次识别请求。

- [ ] **步骤 5：运行测试验证通过**

```bash
cd backend && uv run pytest tests/test_recognizer_factory.py -q
```

预期：PASS（3 项）

需要时打补丁：如果 `test_build_recognizer_yolo_with_existing_model_returns_yolo` 因为 `_ensure_model` 实际尝试加载 fake 文件而失败，使用 `monkeypatch` 把 `YoloRecognizer._ensure_model` 替换为 no-op：

```python
def test_build_recognizer_yolo_with_existing_model_returns_yolo(monkeypatch, tmp_path):
    monkeypatch.setattr(YoloRecognizer, "_ensure_model", lambda self: None)
    # ...其余不变
```

- [ ] **步骤 6：Commit**

```bash
git add backend/app/config.py backend/app/services/recognition.py backend/tests/test_recognizer_factory.py
git commit -m "feat(PicMind): add RECOGNITION_PROVIDER config and build_recognizer factory"
```

---

## 任务 4：把工厂接入 API 与 main

**文件：**
- 修改：`backend/app/api/recognition.py`
- 修改：`backend/app/main.py`

- [ ] **步骤 1：修改 `api/recognition.py` 使用工厂**

修改 `backend/app/api/recognition.py` 第 11-15 行附近：

把：

```python
from app.services.batch_recognition import BatchNotFoundError, BatchRecognitionService, EmptyBatchError
from app.services.recognition import ImageFileMissingError, ImageNotFoundError, RecognitionService

recognition_service = RecognitionService()
```

改为：

```python
from app.config import get_settings
from app.services.batch_recognition import BatchNotFoundError, BatchRecognitionService, EmptyBatchError
from app.services.recognition import (
    ImageFileMissingError,
    ImageNotFoundError,
    RecognitionService,
    build_recognizer,
)

recognition_service = RecognitionService(recognizer=build_recognizer(get_settings()))
```

- [ ] **步骤 2：修改 `main.py` 使用工厂**

修改 `backend/app/main.py`：

把 import 区域追加：

```python
from app.config import get_settings
from app.services.recognition import RecognitionService, build_recognizer
```

把第 35 行附近的：

```python
    app.state.batch_recognition_service = BatchRecognitionService()
```

改为：

```python
    app.state.batch_recognition_service = BatchRecognitionService(
        recognition_service=RecognitionService(recognizer=build_recognizer(get_settings()))
    )
```

- [ ] **步骤 3：运行回归测试**

```bash
cd backend && uv run pytest -q
```

预期：全部通过。`RECOGNITION_PROVIDER` 默认 `mock`，现有用户行为不变。

- [ ] **步骤 4：Commit**

```bash
git add backend/app/api/recognition.py backend/app/main.py
git commit -m "feat(PicMind): wire build_recognizer into API and batch service"
```

---

## 任务 5：Settings API 返回真实 provider

**文件：**
- 修改：`backend/app/api/settings.py`
- 修改：`backend/tests/test_api.py`

- [ ] **步骤 1：编写失败的测试**

在 `backend/tests/test_api.py` 末尾追加：

```python
def test_settings_response_reflects_recognition_provider_default():
    from app.main import create_app
    from fastapi.testclient import TestClient

    client = TestClient(create_app(run_startup_indexing=False, run_batch_worker=False))
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "mock"
```

- [ ] **步骤 2：运行测试验证失败或通过**

```bash
cd backend && uv run pytest tests/test_api.py::test_settings_response_reflects_recognition_provider_default -v
```

如果默认就已经返回 `mock`（硬编码），测试可能通过。这种情况下补一个验证「修改 env 后 provider 跟随」的测试：

```python
def test_settings_response_follows_yolo_env(monkeypatch, tmp_path):
    from app.config import get_settings
    get_settings.cache_clear()
    model_file = tmp_path / "fake.pt"
    model_file.write_bytes(b"x")
    monkeypatch.setenv("RECOGNITION_PROVIDER", "yolo")
    monkeypatch.setenv("YOLO_MODEL_PATH", str(model_file))

    # 阻止 startup 真正加载模型
    from app.services.yolo_recognizer import YoloRecognizer
    monkeypatch.setattr(YoloRecognizer, "_ensure_model", lambda self: None)

    from app.main import create_app
    from fastapi.testclient import TestClient

    client = TestClient(create_app(run_startup_indexing=False, run_batch_worker=False))
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    assert resp.json()["provider"] == "yolo"

    get_settings.cache_clear()
```

运行：

```bash
cd backend && uv run pytest tests/test_api.py -k "settings_response" -v
```

预期：第二个测试 FAIL（当前硬编码 `"mock"`）。

- [ ] **步骤 3：修改 `api/settings.py`**

把：

```python
@router.get("", response_model=SettingsResponse)
def get_app_settings() -> SettingsResponse:
    settings = get_settings()
    return SettingsResponse(
        watch_folders=[str(path) for path in settings.watch_folder_paths],
        db_path=str(settings.db_path),
        provider="mock",
    )
```

改为：

```python
@router.get("", response_model=SettingsResponse)
def get_app_settings() -> SettingsResponse:
    settings = get_settings()
    return SettingsResponse(
        watch_folders=[str(path) for path in settings.watch_folder_paths],
        db_path=str(settings.db_path),
        provider=settings.recognition_provider,
    )
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd backend && uv run pytest tests/test_api.py -k "settings_response" -v
```

预期：两个 settings_response 测试都 PASS。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/api/settings.py backend/tests/test_api.py
git commit -m "feat(PicMind): return dynamic recognition provider in settings API"
```

---

## 任务 6：前端 Settings 页展示动态 provider 文案

**文件：**
- 修改：`frontend/src/pages/Settings.tsx`

- [ ] **步骤 1：更新 Settings.tsx 文案**

把 `frontend/src/pages/Settings.tsx` 第 43-49 行附近：

```tsx
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

改为：

```tsx
      <div className="rounded-xl bg-white p-5 shadow-sm">
        <p className="text-sm text-slate-500">识别 Provider</p>
        <div className="mt-3 flex flex-col gap-3 rounded-lg bg-slate-50 p-4 text-sm text-slate-600">
          <p><span className="font-medium text-slate-900">当前 Provider：</span>{settings.provider}</p>
          {settings.provider === 'yolo' ? (
            <p>使用本地 YOLO11n 模型做物体检测，识别结果包含中文物体名和置信度。</p>
          ) : (
            <p>当前使用本地 Mock 识别，输出基础标签、方向标签和主色标签，未做真实物体检测。</p>
          )}
          <p>修改 Provider 请编辑 backend/.env 中的 RECOGNITION_PROVIDER 后重启后端。</p>
          <p className="font-medium text-amber-700">当前版本不支持在页面切换 Provider。</p>
        </div>
      </div>
```

- [ ] **步骤 2：前端构建验证**

```bash
cd frontend && npm run build
```

预期：BUILD SUCCESS

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/pages/Settings.tsx
git commit -m "feat(PicMind): show provider-specific copy in settings page"
```

---

## 任务 7：前端 ImageDetail 页展示检测到的物体

**文件：**
- 修改：`frontend/src/pages/ImageDetail.tsx`

- [ ] **步骤 1：在 ImageDetail.tsx 追加物体分区**

在 `frontend/src/pages/ImageDetail.tsx` 现有 tags 行（第 50 行附近）之后追加：

```tsx
        {/* 检测到的物体 */}
        {image.objects && image.objects.length > 0 ? (
          <div className="mt-4">
            <p className="text-sm font-medium text-slate-900">检测到的物体</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {image.objects.map((obj, idx) => {
                const name = (obj as Record<string, unknown>).name as string | undefined;
                const label = (obj as Record<string, unknown>).label as string | undefined;
                const confidence = (obj as Record<string, unknown>).confidence as number | undefined;
                if (!label) return null;
                const display = name && name !== label ? `${name}（${label}）` : label;
                const pct = typeof confidence === 'number' ? `· 置信度 ${Math.round(confidence * 100)}%` : '';
                return (
                  <span key={idx} className="rounded-full bg-blue-50 px-3 py-1 text-sm text-blue-700">
                    {display} {pct}
                  </span>
                );
              })}
            </div>
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-400">未检测到物体</p>
        )}
```

注意：现有 `image.objects` 类型是 `Record<string, unknown>[]`，因此用安全转换提取字段；如果未来 client.ts 改为强类型，可以同步简化。

- [ ] **步骤 2：前端构建验证**

```bash
cd frontend && npm run build
```

预期：BUILD SUCCESS（包括 TypeScript 编译通过）

- [ ] **步骤 3：Commit**

```bash
git add frontend/src/pages/ImageDetail.tsx
git commit -m "feat(PicMind): show detected objects on image detail page"
```

---

## 任务 8：Phase 3 手工验证清单

**文件：**
- 创建：`docs/CODEMAPS/yolo-integration-verification.md`

- [ ] **步骤 1：编写验证文档**

创建 `docs/CODEMAPS/yolo-integration-verification.md`：

```markdown
# YOLO11n 集成手工验证清单

## 前置条件

1. `backend/.env` 中设置：
   ```
   RECOGNITION_PROVIDER=yolo
   YOLO_MODEL_PATH=D:/my vibe coding/models/yolo/yolo11n.pt
   YOLO_CONFIDENCE_THRESHOLD=0.25
   ```
2. `ultralytics` 依赖已安装（`cd backend && uv sync`）。
3. 后端已重启。

## 验证步骤

- [ ] `GET /api/settings` 返回 `"provider": "yolo"`。
- [ ] 对一张包含人和车的图片调用 `POST /api/images/{id}/recognize`，响应内 `annotation.objects` 非空。
- [ ] 图片详情页能看到「检测到的物体」分区，包含 `人（person）· 置信度 xx%`。
- [ ] 图片详情页 tags 中包含 `人`、`汽车` 等中文物体名。
- [ ] 图库搜索框输入 `人` 能命中该图片。
- [ ] 图库搜索框输入 `汽车` 能命中该图片。
- [ ] 方向标签和主色标签仍存在。
- [ ] 创建一个批量识别任务覆盖多张图片，全部完成后多张 annotation 的 objects 非空。
- [ ] 把 `RECOGNITION_PROVIDER` 改回 `mock` 并重启后端，应用启动正常，settings 显示 `"provider": "mock"`。
- [ ] 把 `YOLO_MODEL_PATH` 改为不存在的路径并设 `RECOGNITION_PROVIDER=yolo`，重启后端应该报 `YoloModelMissingError` 并打印切换提示，不应静默崩溃。

## 验证日期

YYYY-MM-DD：

## 备注
```

- [ ] **步骤 2：Commit**

```bash
git add docs/CODEMAPS/yolo-integration-verification.md
git commit -m "docs(PicMind): add YOLO integration verification checklist"
```

---

## 任务 9：全量回归

- [ ] **步骤 1：运行后端测试**

```bash
cd backend && uv run pytest -q
```

预期：全部 PASS（包括现有 180+ 测试 + 新增 YOLO 相关测试）。

- [ ] **步骤 2：运行前端构建**

```bash
cd frontend && npm run build
```

预期：BUILD SUCCESS。

- [ ] **步骤 3：如有失败**

如果任何一步失败：
- 阅读完整错误。
- 定位到具体任务和步骤。
- 修复后从步骤 1 重新运行直到全部通过。
- 不要带着失败的测试进入 Phase 3 手工验证。
