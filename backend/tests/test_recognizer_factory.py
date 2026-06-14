from pathlib import Path

import pytest

from app.config import Settings
from app.services.annotation import MockRecognizer
from app.services.recognition import build_recognizer
from app.services.yolo_recognizer import YoloModelMissingError, YoloRecognizer


def test_build_recognizer_returns_mock_by_default():
    settings = Settings(recognition_provider="mock")
    recognizer = build_recognizer(settings)
    assert isinstance(recognizer, MockRecognizer)


def test_build_recognizer_yolo_with_missing_model_raises():
    settings = Settings(
        recognition_provider="yolo",
        yolo_model_path=Path("/definitely/missing/model.pt"),
        yolo_confidence_threshold=0.25,
    )
    with pytest.raises(YoloModelMissingError):
        build_recognizer(settings)


def test_build_recognizer_yolo_with_existing_model_returns_yolo(monkeypatch, tmp_path):
    # 阻止 _ensure_model 真正去 load fake 的 .pt 文件
    monkeypatch.setattr(YoloRecognizer, "_ensure_model", lambda self: None)

    model_file = tmp_path / "yolo11n.pt"
    model_file.write_bytes(b"fake model bytes")

    settings = Settings(
        recognition_provider="yolo",
        yolo_model_path=model_file,
        yolo_confidence_threshold=0.3,
    )

    recognizer = build_recognizer(settings)
    assert isinstance(recognizer, YoloRecognizer)
    assert recognizer.model_path == model_file
    assert recognizer.confidence_threshold == 0.3
