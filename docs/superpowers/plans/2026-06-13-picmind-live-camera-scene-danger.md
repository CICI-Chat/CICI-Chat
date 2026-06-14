# PicMind 实时摄像头识别 + 场景分类 + 危险警告 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 给 PicMind 加一个「实时预览」页面，从本机摄像头读画面、跑 YOLO11n 推理、在浏览器实时显示红框 + 场景标签（indoor/outdoor/unknown）+ 危险物体警告。

**架构：** 后端新增 5 个模块（`live_camera.py` 摄像头封装、`scene_classifier.py` 场景规则、`danger_detector.py` 危险规则、`live_pipeline.py` 串联管线、`api/live.py` WebSocket 端点）；前端新增 `LivePreview.tsx` 页面 + `BboxOverlay.tsx` 共用组件，从 `ImageDetail.tsx` 抽出红框渲染逻辑供两页复用。WebSocket 协议每条消息含 `jpeg_base64 + objects + scene + danger`，前端 `<img>` 标签渲染 base64 + 在容器上叠加 `BboxOverlay` 与原 ImageDetail 完全一致。

**技术栈：** Python 3.14、FastAPI WebSocket、OpenCV `cv2.VideoCapture`、ultralytics YOLO11n、pytest（后端单测）、React 18 + Vite + TypeScript、原生 `WebSocket` API（前端不引第三方库）。

---

## 文件结构

按职责拆分（不按层级）。每个文件单一职责，独立可测。

**后端新建：**
- `backend/app/services/scene_classifier.py` — 输入 objects 列表，输出 `"indoor"` / `"outdoor"` / `"unknown"`。纯函数。
- `backend/app/services/danger_detector.py` — 输入 objects 列表，输出 `{"is_danger": bool, "labels": list[str]}`。纯函数。
- `backend/app/services/live_camera.py` — 封装 `cv2.VideoCapture`：`open` / `read` / `close` + `CameraUnavailableError`。不依赖 FastAPI、不依赖 YOLO。
- `backend/app/services/live_pipeline.py` — 把 LiveCamera + YoloRecognizer + scene_classifier + danger_detector 串成一条迭代器，按 `infer_every_n_frames` 节流推理，yield 出 WebSocket 消息字典。
- `backend/app/api/live.py` — WebSocket 端点 `/api/live/feed`，单连接互斥，客户端断开即释放摄像头。

**后端修改：**
- `backend/app/main.py` — 注册 `live` 路由 + 在 `app.state` 上初始化 `live_lock = asyncio.Lock()` 用于互斥。

**后端测试新建：**
- `backend/tests/test_scene_classifier.py`
- `backend/tests/test_danger_detector.py`
- `backend/tests/test_live_pipeline.py`

**前端新建：**
- `frontend/src/components/BboxOverlay.tsx` — 把 `ImageDetail.tsx` 现有 bbox 渲染逻辑抽出来，接收 `{ objects, className? }` props。
- `frontend/src/pages/LivePreview.tsx` — 新页面：状态机 idle / connecting / running / error；启动按钮、摄像头画面、bbox 叠加、场景条、危险条、停止按钮。

**前端修改：**
- `frontend/src/pages/ImageDetail.tsx` — 把内联 bbox 渲染替换为 `<BboxOverlay objects={image.objects} />`。
- `frontend/src/App.tsx` — `Page` 类型加 `'live'`；导航加按钮；路由分发加 `<LivePreview />`。

**手工验证文档：**
- `docs/CODEMAPS/live-preview-verification.md`

---

## 任务 1：场景分类器（scene_classifier）

**文件：**
- 创建：`backend/app/services/scene_classifier.py`
- 测试：`backend/tests/test_scene_classifier.py`

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_scene_classifier.py`：

```python
from app.services.scene_classifier import classify_scene


def test_indoor_when_furniture_dominates():
    objects = [
        {"label": "couch", "name": "沙发", "confidence": 0.9},
        {"label": "tv", "name": "电视", "confidence": 0.8},
        {"label": "person", "name": "人", "confidence": 0.95},
    ]
    assert classify_scene(objects) == "indoor"


def test_outdoor_when_traffic_dominates():
    objects = [
        {"label": "car", "name": "汽车", "confidence": 0.9},
        {"label": "bus", "name": "公交车", "confidence": 0.85},
        {"label": "person", "name": "人", "confidence": 0.95},
    ]
    assert classify_scene(objects) == "outdoor"


def test_unknown_when_neutral_only():
    objects = [
        {"label": "person", "name": "人", "confidence": 0.95},
        {"label": "dog", "name": "狗", "confidence": 0.7},
    ]
    assert classify_scene(objects) == "unknown"


def test_unknown_when_empty():
    assert classify_scene([]) == "unknown"


def test_unknown_when_tied():
    objects = [
        {"label": "couch", "name": "沙发", "confidence": 0.9},
        {"label": "car", "name": "汽车", "confidence": 0.9},
    ]
    assert classify_scene(objects) == "unknown"


def test_handles_missing_label_field_gracefully():
    objects = [
        {"name": "沙发", "confidence": 0.9},  # 缺 label
        {"label": "tv", "name": "电视", "confidence": 0.8},
    ]
    assert classify_scene(objects) == "indoor"
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd backend && uv run pytest tests/test_scene_classifier.py -q
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.scene_classifier'`

- [ ] **步骤 3：实现 scene_classifier.py**

创建 `backend/app/services/scene_classifier.py`：

```python
"""根据 YOLO 检测物体推断室内/室外/未知场景。

不引入第二个分类模型，纯靠 COCO 物体投票：
- indoor 类物体多 → 'indoor'
- outdoor 类物体多 → 'outdoor'
- 都没命中或打平 → 'unknown'
"""

INDOOR_LABELS = frozenset({
    "chair", "couch", "tv", "laptop", "bed", "dining table",
    "toilet", "refrigerator", "microwave", "oven", "sink",
    "keyboard", "mouse", "book",
})

OUTDOOR_LABELS = frozenset({
    "car", "truck", "bus", "motorcycle", "bicycle",
    "traffic light", "stop sign", "fire hydrant", "bench",
    "bird", "boat", "airplane", "train",
})


def classify_scene(objects: list[dict]) -> str:
    indoor = 0
    outdoor = 0
    for obj in objects:
        label = obj.get("label")
        if label in INDOOR_LABELS:
            indoor += 1
        elif label in OUTDOOR_LABELS:
            outdoor += 1
    if indoor > outdoor:
        return "indoor"
    if outdoor > indoor:
        return "outdoor"
    return "unknown"
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd backend && uv run pytest tests/test_scene_classifier.py -q
```

预期：PASS（6 项）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/scene_classifier.py backend/tests/test_scene_classifier.py
git commit -m "feat(PicMind): add scene classifier (indoor/outdoor/unknown)"
```

---

## 任务 2：危险物体检测器（danger_detector）

**文件：**
- 创建：`backend/app/services/danger_detector.py`
- 测试：`backend/tests/test_danger_detector.py`

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_danger_detector.py`：

```python
from app.services.danger_detector import detect_danger


def test_no_danger_for_empty():
    assert detect_danger([]) == {"is_danger": False, "labels": []}


def test_no_danger_for_safe_objects():
    objects = [
        {"label": "vase", "name": "花瓶", "confidence": 0.8},
        {"label": "book", "name": "书", "confidence": 0.7},
    ]
    assert detect_danger(objects) == {"is_danger": False, "labels": []}


def test_danger_for_person():
    objects = [{"label": "person", "name": "人", "confidence": 0.95}]
    result = detect_danger(objects)
    assert result["is_danger"] is True
    assert "person" in result["labels"]


def test_danger_for_animal():
    objects = [{"label": "dog", "name": "狗", "confidence": 0.85}]
    result = detect_danger(objects)
    assert result["is_danger"] is True
    assert result["labels"] == ["dog"]


def test_danger_dedupes_same_label():
    objects = [
        {"label": "person", "confidence": 0.9},
        {"label": "person", "confidence": 0.85},
        {"label": "person", "confidence": 0.7},
    ]
    result = detect_danger(objects)
    assert result["is_danger"] is True
    assert result["labels"] == ["person"]


def test_danger_keeps_multiple_distinct_labels():
    objects = [
        {"label": "person", "confidence": 0.9},
        {"label": "car", "confidence": 0.85},
        {"label": "vase", "confidence": 0.7},
    ]
    result = detect_danger(objects)
    assert result["is_danger"] is True
    assert sorted(result["labels"]) == ["car", "person"]
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd backend && uv run pytest tests/test_danger_detector.py -q
```

预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：实现 danger_detector.py**

创建 `backend/app/services/danger_detector.py`：

```python
"""判定一组物体是否包含「无人机需要避开」的危险目标。

危险定义：
- 人 / 机动车（汽车、摩托车、自行车、卡车、公交车）
- COCO 动物大类（10 种）
"""

DANGER_LABELS = frozenset({
    "person", "car", "motorcycle", "bicycle", "truck", "bus",
    "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe",
})


def detect_danger(objects: list[dict]) -> dict:
    triggered: set[str] = set()
    for obj in objects:
        label = obj.get("label")
        if label in DANGER_LABELS:
            triggered.add(label)
    return {"is_danger": bool(triggered), "labels": sorted(triggered)}
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd backend && uv run pytest tests/test_danger_detector.py -q
```

预期：PASS（6 项）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/danger_detector.py backend/tests/test_danger_detector.py
git commit -m "feat(PicMind): add danger detector (person/vehicle/animal)"
```

---

## 任务 3：摄像头封装（live_camera）

**文件：**
- 创建：`backend/app/services/live_camera.py`

不写单测——`cv2.VideoCapture` 难以可靠 mock，价值不高；通过任务 4 的 pipeline 测试间接覆盖（注入 fake camera）。

- [ ] **步骤 1：先做 OpenCV 兼容性 spike**

在 backend 目录跑临时验证脚本（不提交）：

```bash
cd backend && uv run python -c "
import cv2
cap = cv2.VideoCapture(0)
ok, frame = cap.read()
print('ok:', ok)
print('frame shape:', frame.shape if ok else None)
cap.release()
"
```

预期：打印 `ok: True` 和形状如 `(720, 1280, 3)`。

- 如果 `ok: False`：标注阻塞，按规格 §7 的应急方案改为 `ultralytics.YOLO(source=0, stream=True)`，并把 LiveCamera/LivePipeline 合并设计后重新进入步骤 2。
- 如果异常 `cv2 not found`：`uv run python -c "import cv2; print(cv2.__version__)"` 检查；ultralytics 已经安装过 opencv-python，应当存在。

- [ ] **步骤 2：实现 live_camera.py**

创建 `backend/app/services/live_camera.py`：

```python
"""摄像头采集封装：开/关/读单帧，线程安全的 read。"""

from threading import Lock
from typing import Optional

import cv2
import numpy as np


class CameraUnavailableError(RuntimeError):
    """摄像头打不开（被占用、未连接、驱动异常）。"""


class LiveCamera:
    def __init__(self, device_index: int = 0) -> None:
        self.device_index = device_index
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = Lock()

    def open(self) -> None:
        with self._lock:
            if self._cap is not None and self._cap.isOpened():
                return
            cap = cv2.VideoCapture(self.device_index)
            if not cap.isOpened():
                cap.release()
                raise CameraUnavailableError(
                    f"无法打开摄像头 device_index={self.device_index}（被占用或未连接）"
                )
            self._cap = cap

    def read(self) -> np.ndarray:
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                raise CameraUnavailableError("摄像头未打开，请先调用 open()")
            ok, frame = self._cap.read()
            if not ok or frame is None:
                raise CameraUnavailableError("摄像头读帧失败（可能已被其他进程接管）")
            return frame

    def close(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
```

- [ ] **步骤 3：手工验证能开能读**

```bash
cd backend && uv run python -c "
from app.services.live_camera import LiveCamera
cam = LiveCamera(0)
cam.open()
frame = cam.read()
print('frame shape:', frame.shape)
cam.close()
print('closed OK')
"
```

预期：打印 `frame shape: (XXX, XXX, 3)` 和 `closed OK`。

- [ ] **步骤 4：Commit**

```bash
git add backend/app/services/live_camera.py
git commit -m "feat(PicMind): add LiveCamera wrapper around cv2.VideoCapture"
```

---

## 任务 4：实时管线（live_pipeline）

**文件：**
- 创建：`backend/app/services/live_pipeline.py`
- 测试：`backend/tests/test_live_pipeline.py`

- [ ] **步骤 1：编写失败的测试**

创建 `backend/tests/test_live_pipeline.py`：

```python
from typing import Iterator

import numpy as np
import pytest

from app.services.annotation import ImageRecognitionInput, RecognitionResult
from app.services.live_pipeline import LivePipeline


class FakeCamera:
    """每次 read 返回固定形状的纯色帧。计数 read 次数。"""

    def __init__(self) -> None:
        self.read_count = 0
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True

    def read(self) -> np.ndarray:
        self.read_count += 1
        # 64x48 BGR 纯红
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        frame[:, :, 2] = 255
        return frame

    def close(self) -> None:
        self.closed = True


class FakeRecognizer:
    """每次 recognize 返回一个固定的 person 检测结果。计数推理次数。"""

    def __init__(self) -> None:
        self.call_count = 0

    def recognize(self, image: ImageRecognitionInput) -> RecognitionResult:
        self.call_count += 1
        return RecognitionResult(
            caption="本地图片",
            tags=["人", "本地图片", "landscape"],
            objects=[{
                "label": "person", "name": "人", "confidence": 0.91,
                "x": 0.3, "y": 0.2, "w": 0.2, "h": 0.6,
            }],
            model_used="yolo11n",
        )


def _take(it: Iterator[dict], n: int) -> list[dict]:
    return [next(it) for _ in range(n)]


def test_pipeline_yields_messages_with_required_fields():
    cam = FakeCamera()
    rec = FakeRecognizer()
    pipeline = LivePipeline(camera=cam, recognizer=rec, infer_every_n_frames=5)

    msg = next(iter(pipeline))

    assert set(msg.keys()) == {"ts", "jpeg_base64", "objects", "scene", "danger"}
    assert isinstance(msg["ts"], float)
    assert isinstance(msg["jpeg_base64"], str) and len(msg["jpeg_base64"]) > 0
    assert msg["objects"][0]["label"] == "person"
    assert msg["scene"] == "unknown"  # 单个 person 不属于 indoor/outdoor 词表
    assert msg["danger"] == {"is_danger": True, "labels": ["person"]}
    pipeline.stop()


def test_pipeline_throttles_inference_every_n_frames():
    cam = FakeCamera()
    rec = FakeRecognizer()
    pipeline = LivePipeline(camera=cam, recognizer=rec, infer_every_n_frames=5)

    msgs = _take(iter(pipeline), 12)

    # 12 帧、每 5 帧推理一次 → 推理调用 ⌈12/5⌉ = 3 次
    assert rec.call_count == 3
    # 12 帧都应当 yield 出消息（中间帧复用上一次推理结果）
    assert len(msgs) == 12
    pipeline.stop()


def test_pipeline_open_close_camera_lifecycle():
    cam = FakeCamera()
    rec = FakeRecognizer()
    pipeline = LivePipeline(camera=cam, recognizer=rec, infer_every_n_frames=5)

    it = iter(pipeline)
    next(it)
    assert cam.opened is True
    assert cam.closed is False

    pipeline.stop()
    assert cam.closed is True
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd backend && uv run pytest tests/test_live_pipeline.py -q
```

预期：FAIL，`ModuleNotFoundError: No module named 'app.services.live_pipeline'`

- [ ] **步骤 3：实现 live_pipeline.py**

创建 `backend/app/services/live_pipeline.py`：

```python
"""把 LiveCamera + Recognizer + 场景/危险判定串成一条消息流迭代器。

设计要点：
- 节流推理：每 N 帧才调用一次 YOLO，中间帧复用上次结果（CPU 上够用）。
- 摄像头由 pipeline 持有 open/close 生命周期，stop() 后保证释放。
- 所有时间戳用 time.time()（实时流不需要 deterministic）。
"""

import base64
import time
import uuid
from typing import Iterator, Protocol

import cv2

from app.services.annotation import ImageRecognitionInput
from app.services.danger_detector import detect_danger
from app.services.scene_classifier import classify_scene


class _CameraLike(Protocol):
    def open(self) -> None: ...
    def read(self): ...
    def close(self) -> None: ...


class _RecognizerLike(Protocol):
    def recognize(self, image: ImageRecognitionInput): ...


class LivePipeline:
    def __init__(
        self,
        camera: _CameraLike,
        recognizer: _RecognizerLike,
        infer_every_n_frames: int = 5,
        jpeg_quality: int = 80,
    ) -> None:
        self._camera = camera
        self._recognizer = recognizer
        self._infer_every = max(1, infer_every_n_frames)
        self._jpeg_quality = jpeg_quality
        self._stopped = False
        self._frame_idx = 0
        # 上一次推理结果缓存（中间帧复用）
        self._last_objects: list[dict] = []
        self._last_scene: str = "unknown"
        self._last_danger: dict = {"is_danger": False, "labels": []}

    def __iter__(self) -> Iterator[dict]:
        self._camera.open()
        try:
            while not self._stopped:
                frame = self._camera.read()
                self._frame_idx += 1

                if (self._frame_idx - 1) % self._infer_every == 0:
                    self._run_inference(frame)

                ok, jpeg_bytes = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._jpeg_quality]
                )
                if not ok:
                    # 编码失败：跳过这一帧，不阻塞流
                    continue

                yield {
                    "ts": time.time(),
                    "jpeg_base64": base64.b64encode(jpeg_bytes.tobytes()).decode("ascii"),
                    "objects": self._last_objects,
                    "scene": self._last_scene,
                    "danger": self._last_danger,
                }
        finally:
            self._camera.close()

    def _run_inference(self, frame) -> None:
        h, w = frame.shape[:2]
        # YoloRecognizer 当前接口要求文件路径。最稳的做法是把这帧写到内存临时文件。
        # cv2.imencode + 给 ultralytics 一个 BGR ndarray 也可以，但需要绕开 YoloRecognizer
        # 的 file_path 接口；为最小改动，这里改用 ndarray 直传。
        # 检测到 path-base 不可行时回退到写 tempfile。
        # 简化：直接走 numpy 路径——见 _recognize_ndarray 注释。
        result = self._recognize_ndarray(frame, w, h)
        self._last_objects = list(result.objects)
        self._last_scene = classify_scene(self._last_objects)
        self._last_danger = detect_danger(self._last_objects)

    def _recognize_ndarray(self, frame, width: int, height: int):
        """为 LivePipeline 设计的 in-memory 推理路径：
        把 ndarray 暂存到 OS 临时目录的随机文件名 → 调 recognizer.recognize → 删除。
        这样 YoloRecognizer 接口不变。
        """
        import os
        import tempfile

        path = os.path.join(tempfile.gettempdir(), f"picmind_live_{uuid.uuid4().hex}.jpg")
        try:
            cv2.imwrite(path, frame)
            return self._recognizer.recognize(
                ImageRecognitionInput(
                    image_id="live",
                    file_path=path,
                    width=width,
                    height=height,
                    format="jpg",
                )
            )
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def stop(self) -> None:
        self._stopped = True
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd backend && uv run pytest tests/test_live_pipeline.py -q
```

预期：PASS（3 项）

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/live_pipeline.py backend/tests/test_live_pipeline.py
git commit -m "feat(PicMind): add LivePipeline (camera+YOLO+scene+danger)"
```

---

## 任务 5：WebSocket 端点（api/live）

**文件：**
- 创建：`backend/app/api/live.py`
- 修改：`backend/app/main.py`

不写自动化测试——WebSocket + 真摄像头的集成测在 CI/pytest 里不现实。手工验证在任务 8。

- [ ] **步骤 1：实现 api/live.py**

创建 `backend/app/api/live.py`：

```python
"""实时摄像头 WebSocket 端点。

协议：每条消息是一条 JSON 文本，结构见 LivePipeline yield 出的 dict。
单连接互斥：第二个客户端连接时立刻关闭并返回 `ALREADY_RUNNING` 原因。
客户端断开时立即停止 pipeline、释放摄像头。
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.services.live_camera import CameraUnavailableError, LiveCamera
from app.services.live_pipeline import LivePipeline
from app.services.recognition import build_recognizer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["live"])


@router.websocket("/api/live/feed")
async def live_feed(websocket: WebSocket) -> None:
    lock: asyncio.Lock = websocket.app.state.live_lock
    if lock.locked():
        await websocket.close(code=1008, reason="ALREADY_RUNNING")
        return

    async with lock:
        await websocket.accept()
        camera = LiveCamera(device_index=0)
        recognizer = build_recognizer(get_settings())
        pipeline = LivePipeline(camera=camera, recognizer=recognizer, infer_every_n_frames=5)

        async def _produce_one() -> dict:
            return await asyncio.to_thread(next, iter(pipeline))

        # __iter__ 是生成器，需要先取到迭代器对象后续复用
        iterator = iter(pipeline)

        async def _next_msg() -> dict:
            return await asyncio.to_thread(next, iterator)

        try:
            while True:
                try:
                    msg = await _next_msg()
                except CameraUnavailableError as exc:
                    await websocket.send_json({"type": "error", "reason": str(exc)})
                    break
                except StopIteration:
                    break
                await websocket.send_text(json.dumps(msg))
        except WebSocketDisconnect:
            logger.info("live feed: client disconnected")
        finally:
            pipeline.stop()
            try:
                await websocket.close()
            except RuntimeError:
                # 已经在断连状态
                pass
```

- [ ] **步骤 2：在 main.py 注册路由 + 初始化锁**

修改 `backend/app/main.py`：

把 import 区域追加：

```python
import asyncio

from app.api import images, live, recognition, reindex, settings, stats
```

把 `create_app` 函数体修改为（在 `app.state.batch_recognition_worker = ...` 之后追加 `app.state.live_lock`，并在 `app.include_router(recognition.router)` 之后追加 live 路由）：

```python
def create_app(run_startup_indexing: bool = True, run_batch_worker: bool = True) -> FastAPI:
    app = FastAPI(title="PicMind", lifespan=create_lifespan(run_startup_indexing, run_batch_worker))
    app.state.batch_recognition_service = BatchRecognitionService(
        recognition_service=RecognitionService(recognizer=build_recognizer(get_settings()))
    )
    app.state.batch_recognition_worker = RecognitionBatchWorker(app.state.batch_recognition_service)
    app.state.live_lock = asyncio.Lock()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(images.router)
    app.include_router(stats.router)
    app.include_router(settings.router)
    app.include_router(reindex.router)
    app.include_router(recognition.router)
    app.include_router(live.router)
    return app
```

- [ ] **步骤 3：运行回归测试**

```bash
cd backend && uv run pytest -q
```

预期：全部通过（含任务 1-4 新增测试 + 现有 161 测试）。

- [ ] **步骤 4：Commit**

```bash
git add backend/app/api/live.py backend/app/main.py
git commit -m "feat(PicMind): add /api/live/feed WebSocket endpoint with single-client lock"
```

---

## 任务 6：抽出 BboxOverlay 共用组件

**文件：**
- 创建：`frontend/src/components/BboxOverlay.tsx`
- 修改：`frontend/src/pages/ImageDetail.tsx`

- [ ] **步骤 1：创建 BboxOverlay.tsx**

创建 `frontend/src/components/BboxOverlay.tsx`：

```tsx
type BoxObject = Record<string, unknown>;

export function BboxOverlay({ objects }: { objects?: BoxObject[] | null }) {
  if (!objects?.length) return null;
  return (
    <>
      {objects.map((obj, idx) => {
        const x = obj.x as number | undefined;
        const y = obj.y as number | undefined;
        const w = obj.w as number | undefined;
        const h = obj.h as number | undefined;
        if (typeof x !== 'number' || typeof y !== 'number'
            || typeof w !== 'number' || typeof h !== 'number') {
          return null;
        }
        const name = (obj.name as string | undefined) ?? (obj.label as string | undefined) ?? '';
        const conf = obj.confidence as number | undefined;
        const pct = typeof conf === 'number' ? `${Math.round(conf * 100)}%` : '';
        return (
          <div
            key={idx}
            className="absolute border-2 border-red-500 pointer-events-none"
            style={{
              left: `${x * 100}%`,
              top: `${y * 100}%`,
              width: `${w * 100}%`,
              height: `${h * 100}%`,
            }}
          >
            <span className="absolute -top-6 left-0 rounded bg-red-500 px-1.5 py-0.5 text-xs text-white whitespace-nowrap">
              {name} {pct}
            </span>
          </div>
        );
      })}
    </>
  );
}
```

- [ ] **步骤 2：修改 ImageDetail.tsx 使用 BboxOverlay**

把 `frontend/src/pages/ImageDetail.tsx` 中现有的 `image.objects?.map(...)` 那一段（红框渲染整段）替换为：

```tsx
        <div className="relative inline-block w-full">
          <img src={image.image_url} alt={image.caption} className="block w-full rounded-xl bg-white object-contain shadow-sm" />
          <BboxOverlay objects={image.objects as Record<string, unknown>[] | undefined} />
        </div>
```

并在文件顶端 import：

```tsx
import { BboxOverlay } from '../components/BboxOverlay';
```

- [ ] **步骤 3：前端构建验证**

```bash
cd frontend && npm run build
```

预期：BUILD SUCCESS。

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/components/BboxOverlay.tsx frontend/src/pages/ImageDetail.tsx
git commit -m "refactor(PicMind): extract BboxOverlay component for reuse"
```

---

## 任务 7：LivePreview 页面 + 导航

**文件：**
- 创建：`frontend/src/pages/LivePreview.tsx`
- 修改：`frontend/src/App.tsx`

- [ ] **步骤 1：创建 LivePreview.tsx**

创建 `frontend/src/pages/LivePreview.tsx`：

```tsx
import { useEffect, useRef, useState } from 'react';
import { BboxOverlay } from '../components/BboxOverlay';

type Status = 'idle' | 'connecting' | 'running' | 'error';

interface FeedMessage {
  ts: number;
  jpeg_base64: string;
  objects: Record<string, unknown>[];
  scene: 'indoor' | 'outdoor' | 'unknown';
  danger: { is_danger: boolean; labels: string[] };
}

const SCENE_TEXT: Record<FeedMessage['scene'], string> = {
  indoor: '🏠 室内',
  outdoor: '🌳 室外',
  unknown: '❓ 未知',
};

export default function LivePreview() {
  const [status, setStatus] = useState<Status>('idle');
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<FeedMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  function start() {
    setStatus('connecting');
    setError(null);
    setMsg(null);
    const ws = new WebSocket('ws://localhost:8000/api/live/feed');
    wsRef.current = ws;

    ws.onopen = () => setStatus('running');
    ws.onmessage = (event) => {
      try {
        const data: FeedMessage = JSON.parse(event.data);
        setMsg(data);
      } catch {
        // 忽略坏帧
      }
    };
    ws.onerror = () => {
      setStatus('error');
      setError('WebSocket 连接失败，请确认后端正在运行');
    };
    ws.onclose = (event) => {
      if (event.code === 1008 && event.reason === 'ALREADY_RUNNING') {
        setStatus('error');
        setError('已有客户端在使用摄像头，请先关闭其他实时预览窗口');
      } else if (status === 'running') {
        setStatus('idle');
      }
    };
  }

  function stop() {
    wsRef.current?.close();
    wsRef.current = null;
    setStatus('idle');
    setMsg(null);
  }

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">实时预览</h2>
        {status === 'idle' && (
          <button
            onClick={start}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white"
          >
            ⊕ 启动摄像头
          </button>
        )}
        {status === 'running' && (
          <button
            onClick={stop}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm text-white"
          >
            停止
          </button>
        )}
      </div>

      {status === 'idle' && !error && (
        <div className="rounded-xl bg-white p-8 text-center text-slate-500 shadow-sm">
          点击「启动摄像头」开始实时识别
        </div>
      )}

      {status === 'connecting' && (
        <div className="rounded-xl bg-white p-8 text-center text-slate-500 shadow-sm">
          正在连接摄像头……
        </div>
      )}

      {status === 'error' && (
        <div className="rounded-xl bg-red-50 p-6 text-sm text-red-700 shadow-sm">
          <p className="font-medium">出错了</p>
          <p className="mt-2">{error}</p>
          <button
            onClick={start}
            className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white"
          >
            重试
          </button>
        </div>
      )}

      {status === 'running' && msg && (
        <>
          <div className="relative inline-block w-full">
            <img
              src={`data:image/jpeg;base64,${msg.jpeg_base64}`}
              alt="实时摄像头画面"
              className="block w-full rounded-xl bg-black object-contain shadow-sm"
            />
            <BboxOverlay objects={msg.objects} />
          </div>

          <div className="flex flex-wrap gap-3 text-sm">
            <div className="rounded-full bg-slate-100 px-4 py-2">
              <span className="font-medium text-slate-900">场景：</span>
              <span className="ml-1">{SCENE_TEXT[msg.scene]}</span>
            </div>
            {msg.danger.is_danger ? (
              <div className="rounded-full bg-red-100 px-4 py-2 text-red-700">
                <span className="font-medium">⚠️ 危险：</span>
                <span className="ml-1">检测到「{msg.danger.labels.join('、')}」（无人机避障目标）</span>
              </div>
            ) : (
              <div className="rounded-full bg-green-100 px-4 py-2 text-green-700">
                ✅ 当前画面无危险目标
              </div>
            )}
          </div>

          <p className="text-xs text-slate-400">
            ⚡ 当前 CPU 推理约 5 FPS。切到 GPU 可达 30 FPS，详见 docs/CODEMAPS/yolo-gpu-migration.md
          </p>
        </>
      )}
    </section>
  );
}
```

- [ ] **步骤 2：修改 App.tsx 加导航**

修改 `frontend/src/App.tsx`：

把：

```tsx
type Page = 'gallery' | 'dashboard' | 'batchHistory' | 'settings';
```

改为：

```tsx
type Page = 'gallery' | 'dashboard' | 'batchHistory' | 'settings' | 'live';
```

把 import 区域追加：

```tsx
import LivePreview from './pages/LivePreview';
```

把：

```tsx
              {(['gallery', 'dashboard', 'batchHistory', 'settings'] as Page[]).map((item) => (
```

改为：

```tsx
              {(['gallery', 'dashboard', 'batchHistory', 'settings', 'live'] as Page[]).map((item) => (
```

把：

```tsx
                  {item === 'gallery' ? '图库' : item === 'dashboard' ? '看板' : item === 'batchHistory' ? '批次历史' : '设置'}
```

改为：

```tsx
                  {item === 'gallery' ? '图库' : item === 'dashboard' ? '看板' : item === 'batchHistory' ? '批次历史' : item === 'settings' ? '设置' : '实时预览'}
```

把：

```tsx
          {page === 'gallery' && <Gallery onSelectImage={setSelectedImageId} />}
          {page === 'dashboard' && <Dashboard />}
          {page === 'batchHistory' && <BatchHistory />}
          {page === 'settings' && <Settings />}
```

改为：

```tsx
          {page === 'gallery' && <Gallery onSelectImage={setSelectedImageId} />}
          {page === 'dashboard' && <Dashboard />}
          {page === 'batchHistory' && <BatchHistory />}
          {page === 'settings' && <Settings />}
          {page === 'live' && <LivePreview />}
```

- [ ] **步骤 3：前端构建验证**

```bash
cd frontend && npm run build
```

预期：BUILD SUCCESS（含 TypeScript 编译）。

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/pages/LivePreview.tsx frontend/src/App.tsx
git commit -m "feat(PicMind): add LivePreview page with WebSocket camera feed"
```

---

## 任务 8：手工验证清单

**文件：**
- 创建：`docs/CODEMAPS/live-preview-verification.md`

- [ ] **步骤 1：编写文档**

创建 `docs/CODEMAPS/live-preview-verification.md`：

```markdown
# 实时预览功能手工验证清单

## 前置条件

- 后端 `.env` 中 `RECOGNITION_PROVIDER=yolo` 且 `YOLO_MODEL_PATH` 指向有效的 yolo11n.pt
- 笔记本/台式机上至少有一个可用摄像头（device_index=0）
- 没有其他程序占用摄像头（关闭视频会议、相机软件、其他浏览器标签页）

## 启动

1. 后端：`cd backend && uv run uvicorn app.main:app --reload`
2. 前端：`cd frontend && npm run dev -- --host 127.0.0.1`
3. 浏览器进 http://localhost:5173/，点顶部导航「实时预览」

## 验证步骤

- [ ] 进入页面默认是 idle 状态，显示「启动摄像头」按钮和「点击启动…」提示
- [ ] 点「启动摄像头」后约 1-3 秒内看到自己的画面
- [ ] 自己的脸/身体被红框圈住，标签写「人 xx%」
- [ ] 桌上放一支笔/书/手机，能看到对应红框（笔可能不在 COCO 类别会被忽略，正常）
- [ ] 场景标签显示「室内」（背景里有显示器/键盘等家具）
- [ ] 危险条亮起红色，labels 含 `person`
- [ ] 把摄像头转向窗外（如能看到车），场景应变为「室外」
- [ ] 拿掉所有人和危险物体（对着空白墙），危险条变绿色「无危险目标」
- [ ] 点「停止」，画面冻结消失，回到 idle 状态
- [ ] 摄像头硬件指示灯（如有）熄灭
- [ ] 重新点「启动」能再次正常工作

## 异常路径验证

- [ ] 启动 PicMind 后端但**不打开**实时预览页面，使用别的程序占用摄像头（例如打开 Windows 自带「相机」应用），再切回浏览器点「启动」→ 应显示错误「无法打开摄像头 device_index=0（被占用或未连接）」
- [ ] 在第一个浏览器标签页正在跑实时预览的同时，开第二个标签页也点「启动」→ 第二个应显示「已有客户端在使用摄像头，请先关闭其他实时预览窗口」
- [ ] 后端没启动的情况下点「启动」→ 显示「WebSocket 连接失败，请确认后端正在运行」+ 重试按钮

## 性能观察

- [ ] CPU 模式下画面约 5 FPS（明显能看出节奏，不流畅但可用）
- [ ] 红框跟随物体移动有约 1 秒延迟（每 5 帧推理一次的节流效果）
- [ ] 后端 CPU 占用单核 ~70-100%，内存稳定不增长

## 验证日期

YYYY-MM-DD：

## 备注
```

- [ ] **步骤 2：Commit**

```bash
git add docs/CODEMAPS/live-preview-verification.md
git commit -m "docs(PicMind): add live-preview verification checklist"
```

---

## 任务 9：全量回归

- [ ] **步骤 1：后端测试**

```bash
cd backend && uv run pytest -q
```

预期：全部通过（含本次新增的 scene_classifier、danger_detector、live_pipeline 测试 + 现有 161 项 = 约 176 项）。

- [ ] **步骤 2：前端构建**

```bash
cd frontend && npm run build
```

预期：BUILD SUCCESS。

- [ ] **步骤 3：如有失败**

- 阅读完整错误。
- 定位到任务和步骤。
- 修复后从步骤 1 重新跑直到全部通过。
- 不要带着失败测试进入手工验证（任务 8）。
