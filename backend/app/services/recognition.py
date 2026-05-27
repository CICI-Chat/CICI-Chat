import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Annotation, Image
from app.services.annotation import ImageRecognitionInput, MockRecognizer, Recognizer


class ImageNotFoundError(Exception):
    """Raised when an image record cannot be found."""


class ImageFileMissingError(Exception):
    """Raised when an image record points to a missing file."""


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
