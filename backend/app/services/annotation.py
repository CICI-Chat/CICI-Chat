from dataclasses import dataclass
from typing import Protocol


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

        return RecognitionResult(
            caption="待分析的本地图片",
            tags=["本地图片", "待分析", orientation],
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
