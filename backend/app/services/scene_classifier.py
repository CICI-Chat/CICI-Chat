"""根据 YOLO 检测物体推断室内/室外场景。

为实时摄像头优化的优先级策略（避免 unknown 过于频繁）：
- 检测到任意室内物体 → 'indoor'（室内优先）
- 否则检测到任意室外物体 → 'outdoor'
- 都没命中 → 默认 'outdoor'（窗外/户外场景最常见）
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
    if indoor > 0:
        return "indoor"
    if outdoor > 0:
        return "outdoor"
    # 检测不到任何室内/室外标志性物体时，默认室外（窗外场景最常见）
    return "outdoor"
