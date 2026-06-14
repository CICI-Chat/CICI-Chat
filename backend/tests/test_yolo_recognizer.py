from pathlib import Path

import pytest
from PIL import Image as PillowImage

from app.services.annotation import ImageRecognitionInput
from app.services.yolo_recognizer import (
    YoloModelMissingError,
    YoloRecognizer,
)


class _FakeTensor:
    """模拟 torch.Tensor 的最小子集：.tolist() 返回嵌套 list。"""

    def __init__(self, data):
        self._data = data

    def tolist(self):
        return self._data


def _make_image_input(file_path: Path, width: int = 640, height: int = 480) -> ImageRecognitionInput:
    return ImageRecognitionInput(
        image_id="test-id",
        file_path=str(file_path),
        width=width,
        height=height,
        format="jpg",
    )


def test_yolo_recognizer_raises_when_model_missing(tmp_path):
    img_path = tmp_path / "img.jpg"
    PillowImage.new("RGB", (10, 10), color=(255, 0, 0)).save(img_path)

    recognizer = YoloRecognizer(model_path="/definitely/not/here.pt", confidence_threshold=0.25)
    with pytest.raises(YoloModelMissingError):
        recognizer.recognize(_make_image_input(img_path))


def test_yolo_recognizer_filters_low_confidence_and_sorts(monkeypatch, tmp_path):
    """fake 模型返回 3 个检测，1 个低于阈值；验证排序和阈值过滤。"""
    img_path = tmp_path / "img.jpg"
    PillowImage.new("RGB", (640, 480), color=(255, 0, 0)).save(img_path)
    model_file = tmp_path / "yolo11n.pt"
    model_file.write_bytes(b"fake model")

    recognizer = YoloRecognizer(model_path=str(model_file), confidence_threshold=0.25)

    class FakeBox:
        def __init__(self, cls_idx: int, conf: float, bbox: tuple[float, float, float, float] = (0.5, 0.5, 0.2, 0.4)) -> None:
            class _T:
                def __init__(self, v): self._v = v
                def item(self): return self._v
            self.cls = [_T(cls_idx)]
            self.conf = [_T(conf)]
            self.xywhn = [_FakeTensor(list(bbox))]

    class FakeResult:
        names = {0: "person", 1: "car", 2: "dog"}
        boxes = [
            FakeBox(0, 0.91, bbox=(0.30, 0.40, 0.20, 0.60)),
            FakeBox(1, 0.84, bbox=(0.70, 0.55, 0.40, 0.30)),
            FakeBox(2, 0.12, bbox=(0.50, 0.50, 0.10, 0.10)),
        ]

    def fake_call(_path, **_kwargs):
        return [FakeResult()]

    def fake_load(self):
        self._model = type("FakeModel", (), {"__call__": staticmethod(fake_call)})()

    monkeypatch.setattr(YoloRecognizer, "_load_model", fake_load)

    result = recognizer.recognize(_make_image_input(img_path))

    assert result.model_used == "yolo11n"
    assert result.caption == "本地图片"
    assert len(result.objects) == 2
    assert result.objects[0]["label"] == "person"
    assert result.objects[0]["name"] == "人"
    assert result.objects[1]["label"] == "car"
    assert result.objects[1]["name"] == "汽车"
    assert "人" in result.tags
    assert "汽车" in result.tags
    assert "狗" not in result.tags
    assert "本地图片" in result.tags
    assert "landscape" in result.tags
    # bbox 字段：person 的中心 (0.30, 0.40) + 宽 0.20 高 0.60 → 左上 (0.20, 0.10)
    person = result.objects[0]
    assert person["x"] == 0.20
    assert person["y"] == 0.10
    assert person["w"] == 0.20
    assert person["h"] == 0.60
    for field in ("x", "y", "w", "h"):
        for obj in result.objects:
            assert isinstance(obj[field], float)
            assert 0.0 <= obj[field] <= 1.0


def test_yolo_recognizer_dedupes_repeated_labels(monkeypatch, tmp_path):
    img_path = tmp_path / "img.jpg"
    PillowImage.new("RGB", (640, 480), color=(0, 0, 255)).save(img_path)
    model_file = tmp_path / "yolo11n.pt"
    model_file.write_bytes(b"fake")

    recognizer = YoloRecognizer(model_path=str(model_file), confidence_threshold=0.25)

    class FakeBox:
        def __init__(self, cls_idx: int, conf: float) -> None:
            class _T:
                def __init__(self, v): self._v = v
                def item(self): return self._v
            self.cls = [_T(cls_idx)]
            self.conf = [_T(conf)]
            self.xywhn = [_FakeTensor([0.5, 0.5, 0.2, 0.4])]

    class FakeResult:
        names = {0: "person"}
        boxes = [FakeBox(0, 0.91), FakeBox(0, 0.88), FakeBox(0, 0.55)]

    def fake_call(_path, **_kwargs):
        return [FakeResult()]

    def fake_load(self):
        self._model = type("FakeModel", (), {"__call__": staticmethod(fake_call)})()

    monkeypatch.setattr(YoloRecognizer, "_load_model", fake_load)

    result = recognizer.recognize(_make_image_input(img_path))

    person_tag_count = sum(1 for t in result.tags if t == "人")
    assert person_tag_count == 1
    assert len(result.objects) == 3
