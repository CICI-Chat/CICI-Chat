# PicMind 实时摄像头识别 + 场景分类 + 危险物体警告

**目标:** 给 PicMind 加一个「实时预览」页面，从本机摄像头读画面、跑 YOLO 识别，在浏览器实时看到红框 + 场景标签 + 危险警告。同时为未来无人机机载视觉做"地面练兵场"——架构与机载场景一致，只换硬件不改代码。

**为什么做这个:** PicMind 当前只能识别静态图。无人机自主感知的核心是处理实时视频流，YOLO 已经集成完毕，差的就是把"静态识别"接上"视频流"。这一步打通后，把代码从 PC 搬到 Pi/Jetson 只需换硬件。

---

## 锁定的范围决策（与用户确认）

| 决策 | 选择 |
|---|---|
| 项目结构 | 在 PicMind 里加，不另开项目 |
| 摄像头来源 | 本机摄像头（`cv2.VideoCapture(0)`） |
| 推理位置 | 后端推理 + WebSocket 推流到前端 |
| 帧率策略 | 每 5 帧跑一次 YOLO，中间帧复用结果 |
| 场景分类实现 | 用 YOLO 物体推断（不引入第二个模型） |
| 危险定义 | 含 `人/汽车/摩托车/自行车/卡车/公交车/COCO 动物大类` 之一 |
| UI 形态 | 顶部导航加「实时预览」单独一页 |
| 启停 | 默认不开，用户点「启动」才开摄像头 |
| 数据持久化 | 不存任何东西 |

## 1. 系统架构

```
┌──────────────┐     WebSocket     ┌──────────────┐
│              │ ───── /api/ ────► │              │
│  浏览器前端    │     live/feed     │   FastAPI    │
│              │                   │   后端        │
│ <img src=    │                   │              │
│  blob URL>   │ ◄── JPEG 帧 ────  │  采集线程：    │
│              │     场景标签        │  cv2 读摄像头  │
│  显示场景标签   │     危险警告        │  ↓           │
│  显示警告条    │                   │  YOLO11n      │
│  [启动][停止] │                   │  每5帧推理一次  │
└──────────────┘                   └──────────────┘
```

未来在无人机上：
- "采集线程：cv2 读摄像头" → 机载电脑 USB 摄像头，**代码 0 改动**
- "YOLO11n 每5帧推理" → GPU 加速到每帧，**代码 0 改动**
- "WebSocket 推流" → 替换为 RTSP / MAVLink

## 2. 数据契约

WebSocket 协议：客户端连接后，服务器以 ~5 Hz 推送二进制消息。每条消息是一个 JSON 文本：

```json
{
  "ts": 1717900800.123,
  "jpeg_base64": "...",
  "objects": [
    {
      "label": "person", "name": "人", "confidence": 0.91,
      "x": 0.31, "y": 0.18, "w": 0.22, "h": 0.64
    }
  ],
  "scene": "indoor",
  "danger": {
    "is_danger": true,
    "labels": ["person"]
  }
}
```

- `jpeg_base64`：原画面（不含红框，红框在前端用 `objects` 自己画，复用 ImageDetail 的逻辑）。
- `objects`：与静态识别完全一致的 dict 形状（label/name/confidence/x/y/w/h）。
- `scene`：`"indoor"` / `"outdoor"` / `"unknown"`。
- `danger`：`is_danger` 是否触发，`labels` 触发的英文标签数组。

**为什么 base64 而不是二进制 frame？**
JSON 不支持二进制混排。后续如有性能压力可改为先发一条 JSON 元数据再发一条二进制 JPEG，本期 YAGNI。

## 3. 后端模块拆分

每个模块单一职责，独立可测：

### 3.1 `backend/app/services/scene_classifier.py`

```python
def classify_scene(objects: list[dict]) -> str:
    """根据 YOLO 输出的物体列表推断场景。

    Returns: 'indoor' / 'outdoor' / 'unknown'
    """
```

**规则（投票制）：**
- `INDOOR_LABELS = {"chair", "couch", "tv", "laptop", "bed", "dining table", "toilet", "refrigerator", "microwave", "oven", "sink", "keyboard", "mouse", "book"}`
- `OUTDOOR_LABELS = {"car", "truck", "bus", "motorcycle", "bicycle", "traffic light", "stop sign", "fire hydrant", "bench", "bird", "boat", "airplane", "train"}`
- 数 `objects` 里命中 INDOOR 的数量 vs OUTDOOR 的数量
- INDOOR 多 → `"indoor"`；OUTDOOR 多 → `"outdoor"`；都为 0 或相等 → `"unknown"`

### 3.2 `backend/app/services/danger_detector.py`

```python
DANGER_LABELS = frozenset({
    "person", "car", "motorcycle", "bicycle", "truck", "bus",
    # COCO 动物大类
    "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe",
})

def detect_danger(objects: list[dict]) -> dict:
    """
    Returns: {"is_danger": bool, "labels": list[str]}
    """
```

去重保留触发的 label 列表。

### 3.3 `backend/app/services/live_camera.py`

```python
class LiveCamera:
    """封装 cv2.VideoCapture 生命周期，线程安全的 read。"""

    def __init__(self, device_index: int = 0): ...
    def open(self) -> None: ...   # 抛 CameraUnavailableError
    def read(self) -> np.ndarray: ...   # BGR
    def close(self) -> None: ...

class CameraUnavailableError(Exception): ...
```

仅做摄像头开关 + 单帧抓取。**不依赖 FastAPI、不依赖 YOLO**。

### 3.4 `backend/app/services/live_pipeline.py`

```python
class LivePipeline:
    """采集 → YOLO（节流）→ 场景 → 危险 → 编码 JPEG → 产出消息。"""

    def __init__(
        self,
        camera: LiveCamera,
        recognizer: YoloRecognizer,
        infer_every_n_frames: int = 5,
        jpeg_quality: int = 80,
    ): ...

    def __iter__(self) -> Iterator[dict]: ...
    def stop(self) -> None: ...
```

迭代器 yield WebSocket 消息字典（结构见第 2 节）。
中间 4 帧复用上一次的 `objects/scene/danger`，只更新 `jpeg_base64`。

### 3.5 `backend/app/api/live.py`

```python
@router.websocket("/api/live/feed")
async def live_feed(websocket: WebSocket): ...
```

- 接受连接 → 检查 `app.state.live_pipeline_lock` 是否被占用 → 占用就 `close(code=1008)` 拒绝
- 否则在后台线程跑 `LivePipeline`，`asyncio.to_thread` 抓帧后 `await ws.send_json`
- 客户端断开 → `pipeline.stop()` + 释放摄像头 + 清锁

`main.py` 注册路由。

## 4. 前端模块

### 4.1 `frontend/src/pages/LivePreview.tsx` 新页面

状态：`idle / connecting / running / error`

UI：
- idle：大按钮「⊕ 启动摄像头」
- connecting：「正在连接…」
- running：摄像头画面 + 实时红框（复用 ImageDetail 的渲染逻辑）+ 场景标签条 + 危险警告条 + 「停止」按钮
- error：错误说明 + 「重试」按钮

WebSocket 连接：`new WebSocket("ws://localhost:8000/api/live/feed")`，
收到消息 → 把 `jpeg_base64` 设给 `<img src={"data:image/jpeg;base64," + ...}>`

红框渲染：把 ImageDetail 中的 bbox 渲染逻辑抽成 `<BboxOverlay objects={...} />` 组件，两个页面共用。

### 4.2 `frontend/src/App.tsx` 导航

顶部 nav 加链接：`图库 | 设置 | 实时预览`

### 4.3 `frontend/src/api/client.ts`

无变化（WebSocket 直接用原生 API，不走 axios）。

## 5. 测试范围

| 测试文件 | 范围 |
|---|---|
| `backend/tests/test_scene_classifier.py` | 喂多种 mock objects，断言 indoor/outdoor/unknown |
| `backend/tests/test_danger_detector.py` | person → True、vase → False、空列表 → False |
| `backend/tests/test_live_pipeline.py` | 用 fake LiveCamera 喂固定帧、fake recognizer 返回固定 objects，断言 yield 出的 dict 结构正确、节流（每 5 帧推理 1 次）行为正确 |
| 前端 `npm run build` | TypeScript 编译通过 |
| 手工验证清单 | 见 §6 |

**不写：**
- ❌ 不写 WebSocket 端到端集成测（依赖真摄像头，pytest 不现实）
- ❌ 不写性能基准测（先看主观体验）
- ❌ 不写 LiveCamera 单测（薄薄的 cv2 包装，单测复现需要 mock cv2.VideoCapture，价值不高）

## 6. 手工验证清单

1. 启动后端：`cd backend && uv run uvicorn app.main:app --reload`
2. 启动前端：`cd frontend && npm run dev -- --host 127.0.0.1`
3. 浏览器进 `http://localhost:5173/live`
4. 点「启动摄像头」
5. 观察：
   - [ ] 看到自己的脸 / 房间画面
   - [ ] 自己的脸有红框 + "人 xx%"
   - [ ] 场景显示 `indoor`（背景里有显示器/键盘等）
   - [ ] 危险条亮起，labels 含 `person`
6. 桌上放手机/笔/书翻翻看，观察识别变化
7. 把摄像头转向窗外（如能看到车），场景变 `outdoor`
8. 点「停止」，画面应该立刻冻结，浏览器到摄像头的连接应断开（摄像头指示灯熄灭）

## 7. Python 3.14 + OpenCV 兼容性预案

项目当前 Python 3.14 + opencv-python 4.13 已经装好（ultralytics 拖进来的）。开工前先写 3 行脚本验证摄像头能开：

```python
import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
print(ret, frame.shape if ret else None)
cap.release()
```

- 能打印帧形状 → 按本规格实现
- 不能 → 改用 `ultralytics.YOLO(source=0, stream=True)` 这条路（ultralytics 内部封装的视频流接口，绕开直接调用 cv2）。架构上把 LivePipeline 的"采集 + 推理"两步合并即可，对前端契约无影响。

## 8. 已知风险与限制

| 风险 | 处理方式 |
|---|---|
| 摄像头被其他程序占用 | 抛 `CameraUnavailableError`，前端展示「摄像头被占用，关闭视频会议/相机软件后重试」 |
| CPU 跑 YOLO 慢 → 画面卡 | 接受 ~5 FPS，前端右下角显示「⚡ 切到 GPU 可达 30 FPS · 见 yolo-gpu-migration.md」 |
| WebSocket 断线 | 前端进入 `error` 状态，点「重试」即可重连 |
| 多客户端同时连 | 第二个连接立即拒绝（code 1008），返回中文原因 `已有客户端在使用摄像头` |

## 9. 不在范围内（明确不做）

- ❌ 录制视频文件
- ❌ 历史回放
- ❌ 多摄像头切换 UI
- ❌ 自动启动（用户必须点按钮）
- ❌ 给画面加航向箭头 / 中心点偏移指示（H4，下一次）
- ❌ 多帧目标追踪 / ID 关联（H3，下一次）
- ❌ 距离估算（H2，下一次）
- ❌ 鉴权（PicMind 是单用户本地工具）

---

## 后续路径预告

完成本次后，PicMind 已经是一个"可以盯着摄像头实时识别 + 提示场景 + 提示危险"的视觉系统。下一步沿着无人机感知主线继续叠加：

1. **H4 中心点偏移**：在画面中心画十字，目标 bbox 中心算出偏移量，输出 `(dx, dy)`——告诉飞控该往哪打舵
2. **H3 多帧追踪**：用 `ultralytics` 自带的 BoT-SORT，给同一个目标在多帧里打同一个 ID
3. **H2 距离估算**：标定 + bbox 高度反推距离

每一步都遵循"在 PicMind 桌面调好，搬到机载零改动"原则。
