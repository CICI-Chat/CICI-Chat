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
