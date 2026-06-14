import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings as PicMindSettings
from app.models import Annotation, Image
from app.services.annotation import ImageRecognitionInput, MockRecognizer, Recognizer


class ImageNotFoundError(Exception):
    """Raised when an image record cannot be found."""


class ImageFileMissingError(Exception):
    """Raised when an image record points to a missing file."""


def build_recognizer(settings: PicMindSettings) -> Recognizer:
    """根据配置返回 Mock 或 YOLO 识别器。

    选择 yolo 时立即调用 ``_ensure_model``，让模型缺失能在启动期就抛
    ``YoloModelMissingError``，而不是延迟到第一次识别请求才暴露。
    """
    if settings.recognition_provider == "yolo":
        try:
            from app.services.yolo_recognizer import YoloRecognizer
        except ImportError as exc:
            raise ImportError(
                "ultralytics is not installed. "
                "Run `uv add ultralytics` in backend/ or switch RECOGNITION_PROVIDER back to mock."
            ) from exc
        recognizer = YoloRecognizer(
            model_path=settings.yolo_model_path,
            confidence_threshold=settings.yolo_confidence_threshold,
        )
        recognizer._ensure_model()
        return recognizer
    return MockRecognizer()


class RecognitionService:
    def __init__(self, recognizer: Recognizer | None = None) -> None:
        self.recognizer = recognizer or MockRecognizer()

    def recognize_image(self, image_id: str, db: Session) -> Image:
        image = db.get(Image, image_id)
        if image is None:
            raise ImageNotFoundError(f"Image not found: {image_id}")

        file_path = Path(image.file_path)
        if not file_path.exists():
            raise ImageFileMissingError(f"Image file missing: {image.file_path}")

        result = self.recognizer.recognize(
            ImageRecognitionInput(
                image_id=image.id,
                file_path=image.file_path,
                width=image.width,
                height=image.height,
                format=image.format,
            )
        )

        if image.annotation is None:
            image.annotation = Annotation(
                image_id=image.id,
                caption=result.caption,
                tags=json.dumps(result.tags, ensure_ascii=False),
                objects=json.dumps(result.objects, ensure_ascii=False),
                model_used=result.model_used,
            )
        else:
            image.annotation.caption = result.caption
            image.annotation.tags = json.dumps(result.tags, ensure_ascii=False)
            image.annotation.objects = json.dumps(result.objects, ensure_ascii=False)
            image.annotation.model_used = result.model_used

        db.commit()
        db.refresh(image)
        return image
