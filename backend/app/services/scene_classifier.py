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
