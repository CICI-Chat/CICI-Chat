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
