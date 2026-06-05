import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image as PillowImage

from app.models import Annotation, Image
from app.services.annotation import ImageRecognitionInput, MockRecognizer, RecognitionResult
from app.services.color_analysis import detect_dominant_color_label
from app.services.recognition import ImageFileMissingError, ImageNotFoundError, RecognitionService


def _image_input(width: int, height: int) -> ImageRecognitionInput:
    return ImageRecognitionInput(
        image_id="image-1",
        file_path="D:/images/example.jpg",
        width=width,
        height=height,
        format="jpeg",
    )


@dataclass
class RecordingRecognizer:
    result: RecognitionResult
    calls: list[ImageRecognitionInput]

    def recognize(self, image: ImageRecognitionInput) -> RecognitionResult:
        self.calls.append(image)
        return self.result


def _stored_image(db_session, path: Path) -> Image:
    image = Image(
        file_path=str(path),
        file_hash="a" * 64,
        file_size=path.stat().st_size if path.exists() else 10,
        width=32,
        height=24,
        format="PNG",
    )
    db_session.add(image)
    db_session.commit()
    db_session.refresh(image)
    return image


def test_mock_recognizer_tags_landscape_images():
    result = MockRecognizer().recognize(_image_input(width=800, height=600))

    assert isinstance(result, RecognitionResult)
    assert result.caption == "待分析的本地图片"
    assert result.tags == ["本地图片", "landscape"]
    assert result.objects == []
    assert result.model_used == "mock"


def test_mock_recognizer_tags_portrait_images():
    result = MockRecognizer().recognize(_image_input(width=600, height=800))

    assert result.tags == ["本地图片", "portrait"]


def test_mock_recognizer_tags_square_images():
    result = MockRecognizer().recognize(_image_input(width=600, height=600))

    assert result.tags == ["本地图片", "square"]


def test_recognition_service_creates_annotation(db_session, sample_image):
    image = _stored_image(db_session, sample_image)
    recognizer = RecordingRecognizer(
        result=RecognitionResult(
            caption="识别完成",
            tags=["本地图片", "landscape"],
            objects=[{"label": "tree", "confidence": 0.8}],
            model_used="fake-model",
        ),
        calls=[],
    )

    refreshed = RecognitionService(recognizer).recognize_image(image.id, db_session)

    assert refreshed.id == image.id
    assert refreshed.annotation is not None
    assert refreshed.annotation.caption == "识别完成"
    assert json.loads(refreshed.annotation.tags) == ["本地图片", "landscape"]
    assert json.loads(refreshed.annotation.objects) == [{"label": "tree", "confidence": 0.8}]
    assert refreshed.annotation.model_used == "fake-model"
    assert recognizer.calls == [
        ImageRecognitionInput(
            image_id=image.id,
            file_path=str(sample_image),
            width=32,
            height=24,
            format="PNG",
        )
    ]


def test_recognition_service_overwrites_existing_annotation(db_session, sample_image):
    image = _stored_image(db_session, sample_image)
    db_session.add(
        Annotation(
            image_id=image.id,
            caption="旧描述",
            tags=json.dumps(["旧标签"], ensure_ascii=False),
            objects=json.dumps([{"label": "old"}], ensure_ascii=False),
            model_used="old-model",
        )
    )
    db_session.commit()
    recognizer = RecordingRecognizer(
        result=RecognitionResult(
            caption="新描述",
            tags=["新标签"],
            objects=[{"label": "new"}],
            model_used="new-model",
        ),
        calls=[],
    )

    refreshed = RecognitionService(recognizer).recognize_image(image.id, db_session)

    assert db_session.query(Annotation).count() == 1
    assert refreshed.annotation.caption == "新描述"
    assert json.loads(refreshed.annotation.tags) == ["新标签"]
    assert json.loads(refreshed.annotation.objects) == [{"label": "new"}]
    assert refreshed.annotation.model_used == "new-model"


def test_recognition_service_raises_for_missing_image(db_session):
    with pytest.raises(ImageNotFoundError, match="missing-image"):
        RecognitionService().recognize_image("missing-image", db_session)


def test_recognition_service_raises_for_missing_file_before_calling_recognizer(db_session, tmp_path):
    missing_path = tmp_path / "missing.png"
    image = _stored_image(db_session, missing_path)
    recognizer = RecordingRecognizer(
        result=RecognitionResult(caption="unused", tags=[], objects=[], model_used="fake"),
        calls=[],
    )

    with pytest.raises(ImageFileMissingError, match=re.escape(str(missing_path))):
        RecognitionService(recognizer).recognize_image(image.id, db_session)

    assert recognizer.calls == []


def test_detect_dominant_color_label_identifies_red(tmp_path):
    path = tmp_path / "red.png"
    PillowImage.new("RGB", (20, 20), color=(255, 0, 0)).save(path)

    assert detect_dominant_color_label(path) == "红色"


def test_detect_dominant_color_label_identifies_yellow(tmp_path):
    path = tmp_path / "yellow.png"
    PillowImage.new("RGB", (20, 20), color=(255, 230, 0)).save(path)

    assert detect_dominant_color_label(path) == "黄色"
