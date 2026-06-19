# H3 多目标追踪与 ID 保持设计

## 背景

PicMind 已经完成实时摄像头识别和 H4 中心点偏移能力：系统可以识别人、车、动物等危险目标，并计算主目标相对画面中心的偏移量。下一步 H3 的目标是让系统在多目标场景下保持稳定身份编号：同一个人或车辆在连续帧中显示同一个 ID，避免无人机因为置信度波动频繁切换追踪目标。

本设计聚焦「同时给所有危险目标编号，并稳定锁定一个主目标」。它不包含手动点击选择目标、距离估算、轨迹尾巴线或真实飞控集成。

## 目标

1. 实时流中的人、车、动物等危险目标拥有稳定 `track_id`。
2. 前端边界框显示 `#1 人 91%` 这类编号标签。
3. 后端维护当前锁定目标 `active_track_id`。
4. `target_offset` 绑定稳定 `track_id`，而不是数组下标。
5. 多目标同框时，锁定目标不因短期置信度波动频繁切换。

## 不在本期范围

- 不做前端点击选择某个目标。
- 不做目标运动轨迹尾巴线。
- 不做距离估算。
- 不接真实飞控。
- 不做多客户端共享同一路视频流。

## 后端设计

### 新增实时追踪器

新增文件：

```text
backend/app/services/yolo_tracker.py
```

`YoloTracker` 专门服务实时摄像头流，和静态图片识别用的 `YoloRecognizer` 分开。

职责：

- 加载 YOLO 模型；
- 接收 OpenCV 摄像头帧；
- 调用 Ultralytics `track(..., persist=True)`；
- 读取 `box.id` 作为 `track_id`；
- 输出与现有 `objects` 兼容的 dict，只新增追踪字段。

输出对象示例：

```json
{
  "track_id": 1,
  "label": "person",
  "name": "人",
  "confidence": 0.91,
  "x": 0.3,
  "y": 0.2,
  "w": 0.2,
  "h": 0.6
}
```

如果某个检测框暂时没有 `box.id`，该目标可以保留 bbox 字段，但不参与 H3 锁定逻辑。

### LivePipeline 改造

`LivePipeline` 增加可选 tracker 依赖。实时流优先使用 tracker 输出带 `track_id` 的 objects；静态 `recognizer` 继续保留给现有图片识别路径，不把 tracking 逻辑塞进 `YoloRecognizer.recognize()`。

新增状态：

```python
self._active_track_id: int | None = None
self._lost_inference_count: int = 0
self._max_lost_inferences: int = 10
```

目标锁定规则：

1. 若没有 active track，从当前危险目标中选择置信度最高且有 `track_id` 的目标。
2. 若 active track 仍在当前 objects 中，继续锁定它，并清零 lost 计数。
3. 若 active track 暂时不在当前 objects 中，递增 lost 计数，不立刻切换目标。
4. lost 计数超过阈值后，清空 active track，再从当前危险目标中重新选择。
5. 只有非危险目标时，不设置 active track。

危险目标仍复用现有 `DANGER_LABELS`。

### WebSocket 消息契约

现有消息字段保持兼容，新增：

```json
"active_track_id": 1
```

`objects` 增加：

```json
"track_id": 1,
"is_active_target": true
```

`target_offset` 增加：

```json
"track_id": 1
```

完整示例：

```json
{
  "ts": 1710000000.123,
  "jpeg_base64": "...",
  "objects": [
    {
      "track_id": 1,
      "label": "person",
      "name": "人",
      "confidence": 0.91,
      "x": 0.3,
      "y": 0.2,
      "w": 0.2,
      "h": 0.6,
      "is_active_target": true
    },
    {
      "track_id": 2,
      "label": "person",
      "name": "人",
      "confidence": 0.88,
      "x": 0.6,
      "y": 0.2,
      "w": 0.2,
      "h": 0.6,
      "is_active_target": false
    }
  ],
  "scene": "outdoor",
  "danger": {"is_danger": true, "labels": ["person"]},
  "frame": {"width": 640, "height": 480, "center": {"x": 0.5, "y": 0.5}},
  "active_track_id": 1,
  "target_offset": {
    "track_id": 1,
    "target_index": 0,
    "label": "person",
    "name": "人",
    "confidence": 0.91,
    "target_center": {"x": 0.4, "y": 0.5},
    "dx": -0.1,
    "dy": 0.0,
    "dx_px": -64,
    "dy_px": 0
  }
}
```

无危险追踪目标时：

```json
"active_track_id": null,
"target_offset": null
```

## 前端设计

### BboxOverlay 增强

`frontend/src/components/BboxOverlay.tsx` 继续负责绘制所有 bbox，但增强显示：

- 有 `track_id` 时，标签显示为 `#1 人 91%`。
- 优先使用 `track_id` 作为 React key，缺失时回退数组下标。
- 每个 `track_id` 使用稳定颜色。
- `is_active_target: true` 的目标使用更粗边框或黄色高亮。

### CenterOffsetOverlay 保持单一职责

`CenterOffsetOverlay` 仍只显示当前锁定目标的中心十字、黄点、箭头和偏移数值。它依赖 `target_offset`，不负责绘制所有目标。

### LivePreview 类型扩展

`FeedMessage` 增加：

```ts
active_track_id?: number | null;
```

object 类型允许：

```ts
track_id?: number;
is_active_target?: boolean;
```

## 测试设计

后端测试不依赖真实摄像头和真实 YOLO，使用 fake tracker 验证 LivePipeline 状态逻辑。

测试覆盖：

1. 同一 `track_id` 连续出现时，`active_track_id` 保持不变。
2. 多个危险目标首次出现时，选择置信度最高的目标。
3. active track 仍存在时，即使另一个目标置信度更高，也不切换。
4. active track 短暂消失时，不立即切换。
5. active track 消失超过阈值后，重新选择新目标。
6. 只有非危险目标时，`active_track_id` 和 `target_offset` 都为 null。
7. `target_offset.track_id` 与 `active_track_id` 一致。
8. 前端 `npm run build` 通过。

## 手工验证

1. 启动后端和前端，进入实时预览页面。
2. 一个人进入画面，显示 `#1 人`，并出现中心偏移 overlay。
3. 第二个人进入画面，显示 `#2 人`，当前锁定目标保持不变。
4. 两个人移动时，各自编号尽量保持稳定。
5. 当前锁定目标短暂离开画面又回来时，尽量恢复原 ID。
6. 当前锁定目标离开超过阈值后，系统重新锁定另一个危险目标。
7. 画面里只有椅子、桌子等非危险目标时，不显示中心偏移 overlay。

## 风险与处理

- Ultralytics 某些检测框可能没有 `box.id`：这类框可以显示，但不参与锁定。
- CPU 模式下追踪帧率低：本期接受低帧率追踪，后续通过 GPU 优化。
- 快速交叉或遮挡可能导致 ID 切换：本期目标是基础 ID 保持，不承诺专业级 ReID。
- 当前推理节流会影响追踪稳定性：保留节流参数，但在文档和验证中说明 CPU 模式限制。
