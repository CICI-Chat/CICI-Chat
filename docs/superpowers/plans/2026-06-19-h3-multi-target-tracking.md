# H3 多目标追踪与 ID 保持实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为 PicMind 实时摄像头流添加多目标追踪能力，让人、车、动物等危险目标拥有稳定 `track_id`，并让当前锁定目标的 `target_offset` 绑定稳定 ID。

**架构：** 新增 `YoloTracker` 作为实时视频追踪器，不污染静态图片用的 `YoloRecognizer`。`LivePipeline` 接收可选 tracker，维护 `active_track_id` 和 lost 计数，前端 `BboxOverlay` 显示 `#ID` 并高亮当前锁定目标。

**技术栈：** Python 3.14、FastAPI、OpenCV、Ultralytics YOLO `track(..., persist=True)`、pytest、React 18、TypeScript、Vite、Tailwind CSS。

---

## 文件结构与职责

- 创建：`backend/app/services/yolo_tracker.py`
  - 实时追踪器；接收 OpenCV frame；调用 Ultralytics `track(..., persist=True)`；输出带 `track_id` 的 object dict。
- 修改：`backend/app/api/live.py`
  - 构造 `YoloTracker` 并传入 `LivePipeline`。
- 修改：`backend/app/services/live_pipeline.py`
  - 支持 tracker 依赖；维护 active track；扩展消息字段 `active_track_id`、`objects[].is_active_target`、`target_offset.track_id`。
- 修改：`backend/tests/test_live_pipeline.py`
  - 使用 fake tracker 覆盖 active track 状态机。
- 创建：`backend/tests/test_yolo_tracker.py`
  - 只测 YOLO track result 到 objects 的纯转换逻辑。
- 修改：`frontend/src/components/BboxOverlay.tsx`
  - 显示 `#ID`，稳定颜色，高亮 active target。
- 修改：`frontend/src/components/CenterOffsetOverlay.tsx`
  - 移除调试 UI，支持 `targetOffset.track_id`。
- 修改：`frontend/src/pages/LivePreview.tsx`
  - 移除调试面板，扩展类型。

---

## 任务 1：新增 YoloTracker 结果转换

**文件：**
- 创建：`backend/app/services/yolo_tracker.py`
- 创建：`backend/tests/test_yolo_tracker.py`

- [ ] **步骤 1：编写失败测试**

创建 `backend/tests/test_yolo_tracker.py`：

```python
class FakeScalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class FakeVector:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class FakeBox:
    def __init__(self, *, cls_id=0, conf=0.9, xywhn=(0.5, 0.5, 0.2, 0.4), track_id=7):
        self.cls = [FakeScalar(cls_id)]
        self.conf = [FakeScalar(conf)]
        self.xywhn = [FakeVector(list(xywhn))]
        self.id = None if track_id is None else [FakeScalar(track_id)]


class FakeResult:
    def __init__(self, boxes, names=None):
        self.boxes = boxes
        self.names = names or {0: "person", 1: "chair"}


def test_track_results_to_objects_includes_track_id_and_bbox():
    from app.services.yolo_tracker import track_results_to_objects

    objects = track_results_to_objects(
        [FakeResult([FakeBox(cls_id=0, conf=0.91, xywhn=(0.4, 0.5, 0.2, 0.6), track_id=3)])],
        confidence_threshold=0.25,
    )

    assert objects == [{
        "track_id": 3,
        "label": "person",
        "name": "人",
        "confidence": 0.91,
        "x": 0.3,
        "y": 0.2,
        "w": 0.2,
        "h": 0.6,
    }]


def test_track_results_to_objects_keeps_box_without_track_id():
    from app.services.yolo_tracker import track_results_to_objects

    objects = track_results_to_objects(
        [FakeResult([FakeBox(cls_id=0, conf=0.91, track_id=None)])],
        confidence_threshold=0.25,
    )

    assert "track_id" not in objects[0]
    assert objects[0]["label"] == "person"


def test_track_results_to_objects_filters_low_confidence():
    from app.services.yolo_tracker import track_results_to_objects

    objects = track_results_to_objects(
        [FakeResult([FakeBox(cls_id=0, conf=0.1, track_id=1)])],
        confidence_threshold=0.25,
    )

    assert objects == []
```

- [ ] **步骤 2：创建最小模块**

创建 `backend/app/services/yolo_tracker.py`：

```python
"""实时摄像头 YOLO 多目标追踪。"""
```

- [ ] **步骤 3：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_yolo_tracker.py -v
```

预期：FAIL，报错包含 `ImportError: cannot import name 'track_results_to_objects'`。

- [ ] **步骤 4：实现 YoloTracker 和转换函数**

将 `backend/app/services/yolo_tracker.py` 替换为：

```python
"""实时摄像头 YOLO 多目标追踪。"""

from pathlib import Path
from threading import Lock

from app.services.yolo_label_map import chinese_name_for_label


class YoloTrackerRuntimeError(Exception):
    """YOLO tracker 运行失败时抛出。"""


class YoloTracker:
    def __init__(self, model_path: str | Path, confidence_threshold: float = 0.25) -> None:
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._lock = Lock()

    def _load_model(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"YOLO model not found: {self.model_path}")
        from ultralytics import YOLO  # noqa: WPS433
        self._model = YOLO(str(self.model_path))

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is None:
                self._load_model()

    def track_frame(self, frame) -> list[dict]:
        self._ensure_model()
        try:
            results = self._model.track(frame, persist=True, verbose=False)
        except Exception as exc:
            raise YoloTrackerRuntimeError(f"YOLO tracking failed: {exc}") from exc
        return track_results_to_objects(results, self.confidence_threshold)


def _track_id_from_box(box) -> int | None:
    track_id = getattr(box, "id", None)
    if track_id is None:
        return None
    try:
        return int(track_id[0].item())
    except (TypeError, IndexError, AttributeError, ValueError):
        return None


def track_results_to_objects(results, confidence_threshold: float) -> list[dict]:
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
            if confidence < confidence_threshold:
                continue
            cx, cy, bw, bh = (float(v) for v in box.xywhn[0].tolist())
            x = max(0.0, cx - bw / 2)
            y = max(0.0, cy - bh / 2)
            obj = {
                "label": label,
                "name": chinese_name_for_label(label),
                "confidence": confidence,
                "x": round(x, 4),
                "y": round(y, 4),
                "w": round(bw, 4),
                "h": round(bh, 4),
            }
            track_id = _track_id_from_box(box)
            if track_id is not None:
                obj["track_id"] = track_id
            objects.append(obj)
    objects.sort(key=lambda item: item["confidence"], reverse=True)
    return objects[:20]
```

- [ ] **步骤 5：运行测试验证通过**

运行：

```bash
cd backend && uv run pytest tests/test_yolo_tracker.py -v
```

预期：3 passed。

- [ ] **步骤 6：Commit**

```bash
git add backend/app/services/yolo_tracker.py backend/tests/test_yolo_tracker.py
git commit -m "feat(H3): add YOLO tracking result conversion"
```

---

## 任务 2：LivePipeline 支持 tracker 和 active_track_id

**文件：**
- 修改：`backend/app/services/live_pipeline.py`
- 修改：`backend/tests/test_live_pipeline.py`

- [ ] **步骤 1：编写失败测试**

在 `backend/tests/test_live_pipeline.py` 的 `FakeRecognizer` 后添加：

```python
class FakeTracker:
    """每次 track_frame 返回预设 objects，并记录调用次数。"""

    def __init__(self, frames: list[list[dict]]) -> None:
        self.frames = frames
        self.call_count = 0

    def track_frame(self, frame) -> list[dict]:
        idx = min(self.call_count, len(self.frames) - 1)
        self.call_count += 1
        return self.frames[idx]
```

在文件末尾添加：

```python
def test_pipeline_uses_tracker_and_emits_active_track_id():
    cam = FakeCamera()
    rec = FakeRecognizer()
    tracker = FakeTracker([[
        {
            "track_id": 7, "label": "person", "name": "人", "confidence": 0.91,
            "x": 0.3, "y": 0.2, "w": 0.2, "h": 0.6,
        }
    ]])
    pipeline = LivePipeline(camera=cam, recognizer=rec, tracker=tracker, infer_every_n_frames=5)

    msg = next(iter(pipeline))

    assert tracker.call_count == 1
    assert rec.call_count == 0
    assert msg["active_track_id"] == 7
    assert msg["objects"][0]["is_active_target"] is True
    assert msg["target_offset"]["track_id"] == 7
    pipeline.stop()
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_live_pipeline.py::test_pipeline_uses_tracker_and_emits_active_track_id -v
```

预期：FAIL，报错包含 `unexpected keyword argument 'tracker'`。

- [ ] **步骤 3：修改 LivePipeline 构造函数和协议**

在 `backend/app/services/live_pipeline.py` 的 `_RecognizerLike` 后添加：

```python
class _TrackerLike(Protocol):
    def track_frame(self, frame) -> list[dict]: ...
```

把 `LivePipeline.__init__` 改为：

```python
    def __init__(
        self,
        camera: _CameraLike,
        recognizer: _RecognizerLike,
        tracker: _TrackerLike | None = None,
        infer_every_n_frames: int = 5,
        jpeg_quality: int = 80,
    ) -> None:
        self._camera = camera
        self._recognizer = recognizer
        self._tracker = tracker
        self._infer_every = max(1, infer_every_n_frames)
        self._jpeg_quality = jpeg_quality
        self._stopped = False
        self._frame_idx = 0
        self._last_objects: list[dict] = []
        self._last_scene: str = "unknown"
        self._last_danger: dict = {"is_danger": False, "labels": []}
        self._last_frame: dict | None = None
        self._last_target_offset: dict | None = None
        self._active_track_id: int | None = None
        self._lost_inference_count = 0
        self._max_lost_inferences = 10
```

- [ ] **步骤 4：修改 _run_inference 优先使用 tracker**

把 `_run_inference()` 开头识别部分改为：

```python
    def _run_inference(self, frame) -> None:
        h, w = frame.shape[:2]
        if self._tracker is not None:
            self._last_objects = list(self._tracker.track_frame(frame))
        else:
            result = self._recognize_ndarray(frame, w, h)
            self._last_objects = list(result.objects)
        self._last_scene = classify_scene(self._last_objects)
        self._last_danger = detect_danger(self._last_objects)
        self._last_frame = {
            "width": w,
            "height": h,
            "center": {"x": 0.5, "y": 0.5},
        }
        self._update_active_track()
        self._mark_active_target()
        self._last_target_offset = self._compute_target_offset(w, h)
```

- [ ] **步骤 5：新增 active track 状态方法**

在 `_compute_target_offset()` 前添加：

```python
    def _danger_objects_with_track(self) -> list[tuple[int, dict]]:
        return [
            (idx, obj)
            for idx, obj in enumerate(self._last_objects)
            if obj.get("label") in DANGER_LABELS and obj.get("track_id") is not None
        ]

    def _update_active_track(self) -> None:
        candidates = self._danger_objects_with_track()
        visible_ids = {obj.get("track_id") for _, obj in candidates}

        if self._active_track_id in visible_ids:
            self._lost_inference_count = 0
            return

        if self._active_track_id is not None:
            self._lost_inference_count += 1
            if self._lost_inference_count <= self._max_lost_inferences:
                return
            self._active_track_id = None
            self._lost_inference_count = 0

        if not candidates:
            return

        _, target = max(candidates, key=lambda pair: pair[1].get("confidence", 0.0))
        self._active_track_id = target.get("track_id")

    def _mark_active_target(self) -> None:
        for obj in self._last_objects:
            obj["is_active_target"] = (
                self._active_track_id is not None
                and obj.get("track_id") == self._active_track_id
            )
```

- [ ] **步骤 6：修改 _compute_target_offset 绑定 active track**

把 `_compute_target_offset()` 中从 `danger_candidates = [` 到 `target_idx, target = max(...)` 的逻辑替换为：

```python
        danger_candidates = self._danger_objects_with_track()

        if self._active_track_id is not None:
            for idx, obj in danger_candidates:
                if obj.get("track_id") == self._active_track_id:
                    target_idx, target = idx, obj
                    break
            else:
                return None
        else:
            if not danger_candidates:
                return None
            target_idx, target = max(
                danger_candidates,
                key=lambda pair: pair[1].get("confidence", 0.0),
            )
```

在 return dict 中加入：

```python
            "track_id": target.get("track_id"),
```

- [ ] **步骤 7：消息增加 active_track_id**

在 `yield` dict 中加入：

```python
                    "active_track_id": self._active_track_id,
```

- [ ] **步骤 8：运行测试确认通过**

运行：

```bash
cd backend && uv run pytest tests/test_live_pipeline.py::test_pipeline_uses_tracker_and_emits_active_track_id -v
```

预期：PASS。

- [ ] **步骤 9：运行 live pipeline 全文件测试**

运行：

```bash
cd backend && uv run pytest tests/test_live_pipeline.py -v
```

预期：所有测试通过。

- [ ] **步骤 10：Commit**

```bash
git add backend/app/services/live_pipeline.py backend/tests/test_live_pipeline.py
git commit -m "feat(H3): add active track state to live pipeline"
```

---

## 任务 3：覆盖目标不跳变和 lost 阈值

**文件：**
- 修改：`backend/tests/test_live_pipeline.py`
- 修改：`backend/app/services/live_pipeline.py`（仅当测试暴露缺陷时）

- [ ] **步骤 1：新增多目标不切换测试**

在 `backend/tests/test_live_pipeline.py` 末尾添加：

```python
def test_active_track_does_not_switch_when_new_target_has_higher_confidence():
    cam = FakeCamera()
    rec = FakeRecognizer()
    tracker = FakeTracker([
        [{
            "track_id": 1, "label": "person", "name": "人", "confidence": 0.80,
            "x": 0.2, "y": 0.2, "w": 0.2, "h": 0.6,
        }],
        [
            {
                "track_id": 1, "label": "person", "name": "人", "confidence": 0.70,
                "x": 0.2, "y": 0.2, "w": 0.2, "h": 0.6,
            },
            {
                "track_id": 2, "label": "person", "name": "人", "confidence": 0.99,
                "x": 0.6, "y": 0.2, "w": 0.2, "h": 0.6,
            },
        ],
    ])
    pipeline = LivePipeline(camera=cam, recognizer=rec, tracker=tracker, infer_every_n_frames=1)

    msgs = _take(iter(pipeline), 2)

    assert msgs[0]["active_track_id"] == 1
    assert msgs[1]["active_track_id"] == 1
    assert msgs[1]["target_offset"]["track_id"] == 1
    pipeline.stop()
```

- [ ] **步骤 2：新增 lost 后重选测试**

继续添加：

```python
def test_active_track_reacquires_after_lost_threshold():
    cam = FakeCamera()
    rec = FakeRecognizer()
    tracker = FakeTracker([
        [{
            "track_id": 1, "label": "person", "name": "人", "confidence": 0.90,
            "x": 0.2, "y": 0.2, "w": 0.2, "h": 0.6,
        }],
        [],
        [],
        [{
            "track_id": 2, "label": "person", "name": "人", "confidence": 0.95,
            "x": 0.6, "y": 0.2, "w": 0.2, "h": 0.6,
        }],
    ])
    pipeline = LivePipeline(camera=cam, recognizer=rec, tracker=tracker, infer_every_n_frames=1)
    pipeline._max_lost_inferences = 2

    msgs = _take(iter(pipeline), 4)

    assert msgs[0]["active_track_id"] == 1
    assert msgs[1]["active_track_id"] == 1
    assert msgs[1]["target_offset"] is None
    assert msgs[2]["active_track_id"] == 1
    assert msgs[2]["target_offset"] is None
    assert msgs[3]["active_track_id"] == 2
    assert msgs[3]["target_offset"]["track_id"] == 2
    pipeline.stop()
```

- [ ] **步骤 3：运行新增测试**

运行：

```bash
cd backend && uv run pytest tests/test_live_pipeline.py::test_active_track_does_not_switch_when_new_target_has_higher_confidence tests/test_live_pipeline.py::test_active_track_reacquires_after_lost_threshold -v
```

预期：PASS。若第二个测试显示第 4 帧仍是 1，调整 `_update_active_track()`：当 lost 超阈值且当前 candidates 非空时，同一轮应立即选择新 candidate。

- [ ] **步骤 4：运行完整 live pipeline 测试**

运行：

```bash
cd backend && uv run pytest tests/test_live_pipeline.py -v
```

预期：所有测试通过。

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/live_pipeline.py backend/tests/test_live_pipeline.py
git commit -m "test(H3): cover active track stability and reacquire"
```

---

## 任务 4：实时 API 接入 YoloTracker

**文件：**
- 修改：`backend/app/api/live.py`
- 测试：`backend/tests/test_live_pipeline.py`、`backend/tests/test_yolo_tracker.py`

- [ ] **步骤 1：修改 live.py 导入**

在 `backend/app/api/live.py` 添加：

```python
from app.services.yolo_tracker import YoloTracker
```

- [ ] **步骤 2：构造 tracker 并传入 pipeline**

把：

```python
        recognizer = build_recognizer(get_settings())
        pipeline = LivePipeline(camera=camera, recognizer=recognizer, infer_every_n_frames=5)
```

替换为：

```python
        settings = get_settings()
        recognizer = build_recognizer(settings)
        tracker = None
        if settings.recognition_provider == "yolo":
            tracker = YoloTracker(
                model_path=settings.yolo_model_path,
                confidence_threshold=settings.yolo_confidence_threshold,
            )
            tracker._ensure_model()
        pipeline = LivePipeline(
            camera=camera,
            recognizer=recognizer,
            tracker=tracker,
            infer_every_n_frames=5,
        )
```

- [ ] **步骤 3：运行后端相关测试**

运行：

```bash
cd backend && uv run pytest tests/test_live_pipeline.py tests/test_yolo_tracker.py -v
```

预期：全部通过。

- [ ] **步骤 4：Commit**

```bash
git add backend/app/api/live.py
git commit -m "feat(H3): use YOLO tracker in live feed"
```

---

## 任务 5：前端显示 track ID 和 active 高亮

**文件：**
- 修改：`frontend/src/components/BboxOverlay.tsx`
- 修改：`frontend/src/components/CenterOffsetOverlay.tsx`
- 修改：`frontend/src/pages/LivePreview.tsx`

- [ ] **步骤 1：改造 BboxOverlay**

将 `frontend/src/components/BboxOverlay.tsx` 替换为：

```tsx
type BoxObject = Record<string, unknown>;

const TRACK_COLORS = [
  'border-red-500 bg-red-500',
  'border-sky-500 bg-sky-500',
  'border-emerald-500 bg-emerald-500',
  'border-fuchsia-500 bg-fuchsia-500',
  'border-orange-500 bg-orange-500',
  'border-violet-500 bg-violet-500',
];

function colorForTrack(trackId: number | undefined) {
  if (typeof trackId !== 'number') return 'border-red-500 bg-red-500';
  return TRACK_COLORS[Math.abs(trackId) % TRACK_COLORS.length];
}

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
        const trackId = obj.track_id as number | undefined;
        const active = obj.is_active_target === true;
        const name = (obj.name as string | undefined) ?? (obj.label as string | undefined) ?? '';
        const conf = obj.confidence as number | undefined;
        const pct = typeof conf === 'number' ? `${Math.round(conf * 100)}%` : '';
        const color = colorForTrack(trackId);
        const [borderColor, bgColor] = color.split(' ');
        const label = typeof trackId === 'number' ? `#${trackId} ${name} ${pct}` : `${name} ${pct}`;
        return (
          <div
            key={typeof trackId === 'number' ? `track-${trackId}` : `box-${idx}`}
            className={`absolute pointer-events-none ${borderColor} ${active ? 'border-4' : 'border-2'}`}
            style={{
              left: `${x * 100}%`,
              top: `${y * 100}%`,
              width: `${w * 100}%`,
              height: `${h * 100}%`,
            }}
          >
            <span className={`absolute -top-6 left-0 rounded px-1.5 py-0.5 text-xs text-white whitespace-nowrap ${active ? 'bg-yellow-500' : bgColor}`}>
              {active ? '锁定 ' : ''}{label}
            </span>
          </div>
        );
      })}
    </>
  );
}
```

- [ ] **步骤 2：清理 CenterOffsetOverlay 调试 UI**

在 `frontend/src/components/CenterOffsetOverlay.tsx`：

1. 在 `TargetOffset` 增加：

```ts
  track_id?: number;
```

2. 删除 `debugInfo` 相关代码。

3. 把没有 target 时逻辑改为：

```tsx
  if (!safeOffset) {
    return null;
  }
```

4. 把左上角目标文字改为：

```tsx
          目标：{safeOffset.track_id ? `#${safeOffset.track_id} ` : ''}{safeOffset.name || safeOffset.label || '未知'}{' '}
```

- [ ] **步骤 3：清理 LivePreview 调试面板并扩展类型**

在 `frontend/src/pages/LivePreview.tsx`：

1. `TargetOffset` 增加：

```ts
  track_id?: number;
```

2. `FeedMessage` 增加：

```ts
  active_track_id?: number | null;
```

3. 删除运行态中的紫色调试面板：

```tsx
          {/* 🔧 调试：打印完整消息结构 */}
          <div className="mb-2 rounded bg-purple-900/80 p-2 text-xs text-white">
            ...
          </div>
```

- [ ] **步骤 4：运行前端构建**

运行：

```bash
cd frontend && npm run build
```

预期：TypeScript 和 Vite build 通过。

- [ ] **步骤 5：Commit**

```bash
git add frontend/src/components/BboxOverlay.tsx frontend/src/components/CenterOffsetOverlay.tsx frontend/src/pages/LivePreview.tsx
git commit -m "feat(H3): show track IDs in live preview"
```

---

## 任务 6：完整验证与文档更新

**文件：**
- 修改：`docs/CODEMAPS/live-preview-verification.md`

- [ ] **步骤 1：更新手工验证清单**

在 `docs/CODEMAPS/live-preview-verification.md` 追加 H3 验证段落：

```markdown
## H3 多目标追踪验证

- [ ] 一个人进入画面，bbox 标签显示 `#<id> 人`。
- [ ] 第二个人进入画面，两个目标显示不同编号。
- [ ] 当前锁定目标标签显示「锁定」。
- [ ] 当前锁定目标的中心十字、黄点、箭头和偏移数值正常显示。
- [ ] 已锁定目标还在画面中时，另一个人靠近或置信度更高也不立即切换锁定。
- [ ] 已锁定目标离开画面后，中心偏移 overlay 消失；超过阈值后重新锁定新的危险目标。
- [ ] 画面里只有椅子、桌子等非危险物体时，不显示中心偏移 overlay。
```

- [ ] **步骤 2：运行后端完整测试**

运行：

```bash
cd backend && uv run pytest -v
```

预期：全部通过。

- [ ] **步骤 3：运行前端构建**

运行：

```bash
cd frontend && npm run build
```

预期：构建通过。

- [ ] **步骤 4：手工运行验证**

启动：

```bash
cd backend && uv run uvicorn app.main:app --reload --port 8000
```

另开终端：

```bash
cd frontend && npm run dev -- --host 127.0.0.1
```

浏览器打开实时预览页，按 H3 清单验证。若因 CPU 较慢出现卡顿，记录为已知性能限制，不在本任务优化。

- [ ] **步骤 5：Commit**

```bash
git add docs/CODEMAPS/live-preview-verification.md
git commit -m "docs(H3): add multi-target tracking verification checklist"
```

---

## 自检结果

- 规格覆盖度：覆盖新增 tracker、LivePipeline active track、WebSocket 契约、前端 ID 展示、测试、手工验证。
- 占位符扫描：没有 TODO、待定、类似任务等占位表达。
- 类型一致性：后端统一使用 `track_id`、`active_track_id`、`is_active_target`；前端使用同名字段。
- 范围控制：未包含点击选择、距离估算、轨迹尾巴线、飞控集成。
