import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image as PillowImage

from app.models import Annotation, Image
from app.services.annotation import ImageRecognitionInput, MockRecognizer, RecognitionResult
from app.services.color_analysis import COLOR_PALETTE, detect_dominant_color_label
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


def test_mock_recognizer_tags_landscape_images(tmp_path):
    path = tmp_path / "landscape-light-yellow.png"
    PillowImage.new("RGB", (80, 60), color=(254, 249, 195)).save(path)

    result = MockRecognizer().recognize(
        ImageRecognitionInput(
            image_id="image-1",
            file_path=str(path),
            width=800,
            height=600,
            format="PNG",
        )
    )

    assert isinstance(result, RecognitionResult)
    assert result.caption == "待分析的本地图片"
    assert result.tags == ["本地图片", "landscape", "浅黄色"]
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


def test_mock_recognizer_keeps_orientation_when_color_analysis_fails(tmp_path):
    path = tmp_path / "broken.png"
    path.write_text("not an image", encoding="utf-8")

    result = MockRecognizer().recognize(
        ImageRecognitionInput(
            image_id="image-1",
            file_path=str(path),
            width=800,
            height=600,
            format="PNG",
        )
    )

    assert result.tags == ["本地图片", "landscape"]


def test_recognition_service_persists_mock_color_tag(db_session, tmp_path):
    image_path = tmp_path / "dark-blue-service.png"
    PillowImage.new("RGB", (32, 24), color=(30, 58, 138)).save(image_path)
    image = _stored_image(db_session, image_path)

    refreshed = RecognitionService(MockRecognizer()).recognize_image(image.id, db_session)

    assert json.loads(refreshed.annotation.tags) == ["本地图片", "landscape", "深蓝色"]
    assert "待分析" not in json.loads(refreshed.annotation.tags)


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


@pytest.mark.parametrize(
    ("rgb", "expected_label"),
    [
        ((254, 202, 202), "浅红色"),
        ((220, 20, 60), "红色"),
        ((127, 29, 29), "深红色"),
        ((254, 215, 170), "浅橙色"),
        ((255, 140, 0), "橙色"),
        ((124, 45, 18), "深橙色"),
        ((254, 249, 195), "浅黄色"),
        ((255, 215, 0), "黄色"),
        ((113, 63, 18), "深黄色"),
        ((187, 247, 208), "浅绿色"),
        ((34, 139, 34), "绿色"),
        ((20, 83, 45), "深绿色"),
        ((207, 250, 254), "浅青色"),
        ((6, 182, 212), "青色"),
        ((21, 94, 117), "深青色"),
        ((191, 219, 254), "浅蓝色"),
        ((30, 144, 255), "蓝色"),
        ((30, 58, 138), "深蓝色"),
        ((233, 213, 255), "浅紫色"),
        ((128, 0, 128), "紫色"),
        ((88, 28, 135), "深紫色"),
        ((252, 231, 243), "浅粉色"),
        ((255, 105, 180), "粉色"),
        ((131, 24, 67), "深粉色"),
        ((231, 209, 185), "浅棕色"),
        ((139, 69, 19), "棕色"),
        ((67, 36, 17), "深棕色"),
        ((229, 231, 235), "浅灰色"),
        ((128, 128, 128), "灰色"),
        ((31, 41, 55), "深灰色"),
        ((0, 0, 0), "黑色"),
        ((255, 255, 255), "白色"),
    ],
)
def test_detect_dominant_color_label_identifies_refined_palette(tmp_path, rgb, expected_label):
    path = tmp_path / f"{expected_label}.png"
    PillowImage.new("RGB", (20, 20), color=rgb).save(path)

    assert detect_dominant_color_label(path) == expected_label


@pytest.mark.parametrize(
    ("rgb", "expected_label"),
    [
        ((248, 190, 190), "浅红色"),
        ((100, 25, 25), "深红色"),
        ((245, 205, 150), "浅橙色"),
        ((120, 45, 18), "深橙色"),
        ((245, 240, 180), "浅黄色"),
        ((90, 55, 20), "深黄色"),
        ((170, 235, 195), "浅绿色"),
        ((18, 70, 42), "深绿色"),
        ((190, 240, 245), "浅青色"),
        ((18, 82, 100), "深青色"),
        ((175, 210, 245), "浅蓝色"),
        ((25, 50, 120), "深蓝色"),
        ((220, 200, 245), "浅紫色"),
        ((75, 25, 120), "深紫色"),
        ((245, 220, 235), "浅粉色"),
        ((115, 25, 60), "深粉色"),
        ((215, 190, 165), "浅棕色"),
        ((60, 35, 20), "深棕色"),
        ((215, 218, 225), "浅灰色"),
        ((35, 45, 60), "深灰色"),
    ],
)
def test_detect_dominant_color_label_identifies_nearby_refined_colors(tmp_path, rgb, expected_label):
    path = tmp_path / f"nearby-{expected_label}.png"
    PillowImage.new("RGB", (20, 20), color=rgb).save(path)

    assert detect_dominant_color_label(path) == expected_label


def test_detect_dominant_color_label_handles_pale_light_green(tmp_path):
    path = tmp_path / "pale-light-green.png"
    PillowImage.new("RGB", (20, 20), color=(220, 255, 225)).save(path)

    assert detect_dominant_color_label(path) == "浅绿色"


def test_detect_dominant_color_label_keeps_near_white_from_pastels(tmp_path):
    path = tmp_path / "near-white.png"
    PillowImage.new("RGB", (20, 20), color=(245, 245, 245)).save(path)

    assert detect_dominant_color_label(path) == "白色"


def test_refined_palette_excludes_skin_tone_labels():
    labels = {label for label, _rgb in COLOR_PALETTE}

    assert "肉色" not in labels
    assert "肤色" not in labels
