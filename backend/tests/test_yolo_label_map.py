from app.services.yolo_label_map import COCO_LABEL_TO_CHINESE_NAME, chinese_name_for_label


def test_chinese_name_for_label_known():
    assert chinese_name_for_label("person") == "人"
    assert chinese_name_for_label("car") == "汽车"
    assert chinese_name_for_label("dog") == "狗"


def test_chinese_name_for_label_unknown_fallback():
    assert chinese_name_for_label("nonexistent_label") == "nonexistent_label"


def test_coco_label_count():
    assert len(COCO_LABEL_TO_CHINESE_NAME) == 80
