import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from sqlalchemy.orm import Session

from app.services.recognition import RecognitionService

logger = logging.getLogger(__name__)


class BatchNotFoundError(Exception):
    """Raised when a batch job cannot be found."""


class EmptyBatchError(Exception):
    """Raised when a batch job is requested without images."""


@dataclass
class BatchJob:
    batch_id: str
    image_ids: list[str]
    total: int
    completed: int
    failed: int
    pending: int
    running: int
    status: str


class ImageRecognitionService(Protocol):
    def recognize_image(self, image_id: str, db: Session) -> object: ...


class BatchRecognitionService:
    def __init__(self, recognition_service: ImageRecognitionService | None = None) -> None:
        self.recognition_service = recognition_service or RecognitionService()
        self._batches: dict[str, BatchJob] = {}

    def create_batch(self, image_ids: list[str]) -> BatchJob:
        if not image_ids:
            raise EmptyBatchError("Batch must include at least one image")

        job = BatchJob(
            batch_id=str(uuid4()),
            image_ids=list(image_ids),
            total=len(image_ids),
            completed=0,
            failed=0,
            pending=len(image_ids),
            running=0,
            status="pending",
        )
        self._batches[job.batch_id] = job
        return job

    def get_batch(self, batch_id: str) -> BatchJob:
        try:
            return self._batches[batch_id]
        except KeyError as exc:
            raise BatchNotFoundError(f"Batch not found: {batch_id}") from exc

    def run_batch(self, batch_id: str, db: Session) -> BatchJob:
        job = self.get_batch(batch_id)
        if job.status != "pending":
            return job

        for image_id in job.image_ids:
            job.pending -= 1
            job.running += 1
            job.status = "running"

            try:
                self.recognition_service.recognize_image(image_id, db)
            except Exception:
                db.rollback()
                logger.exception(
                    "Recognition failed while running batch",
                    extra={"batch_id": job.batch_id, "image_id": image_id},
                )
                job.failed += 1
            else:
                job.completed += 1
            finally:
                job.running -= 1

        job.status = "failed" if job.failed else "completed"
        return job
