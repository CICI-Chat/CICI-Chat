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


def test_outdoor_when_neutral_only():
    """只有中性物体（人/动物/等）时，默认室外。"""
    objects = [
        {"label": "person", "name": "人", "confidence": 0.95},
        {"label": "dog", "name": "狗", "confidence": 0.7},
    ]
    assert classify_scene(objects) == "outdoor"


def test_outdoor_when_empty():
    """什么都没检测到时默认室外（天空/白墙/窗外场景）。"""
    assert classify_scene([]) == "outdoor"


def test_indoor_when_tied():
    """只要检测到哪怕一个室内物体，优先判定为室内。"""
    objects = [
        {"label": "couch", "name": "沙发", "confidence": 0.9},
        {"label": "car", "name": "汽车", "confidence": 0.9},
    ]
    assert classify_scene(objects) == "indoor"


def test_handles_missing_label_field_gracefully():
    objects = [
        {"name": "沙发", "confidence": 0.9},
        {"label": "tv", "name": "电视", "confidence": 0.8},
    ]
    assert classify_scene(objects) == "indoor"
