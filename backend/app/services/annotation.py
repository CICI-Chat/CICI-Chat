from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.services.color_analysis import detect_dominant_color_label


@dataclass(frozen=True)
class ImageRecognitionInput:
    image_id: str
    file_path: str
    width: int
    height: int
    format: str


@dataclass(frozen=True)
class RecognitionResult:
    caption: str
    tags: list[str]
    objects: list[dict[str, object]]
    model_used: str


class Recognizer(Protocol):
    def recognize(self, image: ImageRecognitionInput) -> RecognitionResult:
        """Return recognition metadata for an image."""


class MockRecognizer:
    def recognize(self, image: ImageRecognitionInput) -> RecognitionResult:
        if image.width > image.height:
            orientation = "landscape"
        elif image.height > image.width:
            orientation = "portrait"
        else:
            orientation = "square"

        tags = ["本地图片", orientation]
        file_path = Path(image.file_path)
        if file_path.exists() and file_path.is_file():
            color_label = detect_dominant_color_label(file_path)
            if color_label is not None:
                tags.append(color_label)

        return RecognitionResult(
            caption="待分析的本地图片",
            tags=tags,
            objects=[],
            model_used="mock",
        )


@dataclass(frozen=True)
class MockAnnotation:
    caption: str
    tags: list[str]
    objects: list[dict[str, object]]
    model_used: str


def create_mock_annotation() -> MockAnnotation:
    return MockAnnotation(
        caption="待分析的本地图片",
        tags=["本地图片", "待分析"],
        objects=[],
        model_used="mock",
    )
