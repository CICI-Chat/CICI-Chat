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
        {"name": "沙发", "confidence": 0.9},
        {"label": "tv", "name": "电视", "confidence": 0.8},
    ]
    assert classify_scene(objects) == "indoor"
