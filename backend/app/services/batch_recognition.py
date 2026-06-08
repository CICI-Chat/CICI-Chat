import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from time import sleep
from typing import Protocol

from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker

from app.database import SessionLocal
from app.models import Image, RecognitionBatch, RecognitionBatchItem
from app.schemas import (
    FailureCategory,
    RecognitionBatchItemImage,
    RecognitionBatchItemList,
    RecognitionBatchItemResponse,
    RecognitionBatchList,
    RecognitionBatchResponse,
)
from app.services.recognition import RecognitionService

logger = logging.getLogger(__name__)

BATCH_STATUS_QUEUED = "queued"
BATCH_STATUS_RUNNING = "running"
BATCH_STATUS_PAUSED = "paused"
BATCH_STATUS_CANCELLED = "cancelled"
BATCH_STATUS_COMPLETED = "completed"
BATCH_STATUS_FAILED = "failed"

ITEM_STATUS_QUEUED = "queued"
ITEM_STATUS_RUNNING = "running"
ITEM_STATUS_COMPLETED = "completed"
ITEM_STATUS_FAILED = "failed"
ITEM_STATUS_CANCELLED = "cancelled"

TERMINAL_BATCH_STATUSES = {BATCH_STATUS_CANCELLED, BATCH_STATUS_COMPLETED, BATCH_STATUS_FAILED}


class BatchNotFoundError(Exception):
    pass


class EmptyBatchError(Exception):
    pass


class ImageRecognitionService(Protocol):
    def recognize_image(self, image_id: str, db: Session) -> object: ...


SessionFactory = Callable[[], Session]


def utc_now() -> datetime:
    return datetime.now(UTC)


class BatchRecognitionService:
    def __init__(
        self,
        recognition_service: ImageRecognitionService | None = None,
        session_factory: SessionFactory | sessionmaker[Session] = SessionLocal,
    ) -> None:
        self.recognition_service = recognition_service or RecognitionService()
        self.session_factory = session_factory

    def create_batch(self, db: Session, image_ids: list[str]) -> RecognitionBatch:
        image_ids = list(dict.fromkeys(image_ids))
        if not image_ids:
            raise EmptyBatchError("Batch must include at least one image")

        batch = RecognitionBatch(
            status=BATCH_STATUS_QUEUED,
            total=len(image_ids),
            completed=0,
            failed=0,
            cancelled=0,
        )
        batch.items = [RecognitionBatchItem(image_id=image_id, status=ITEM_STATUS_QUEUED) for image_id in image_ids]
        db.add(batch)
        db.commit()
        db.refresh(batch)
        return batch

    def get_batch_progress(self, db: Session, batch_id: str) -> RecognitionBatchResponse:
        batch = self._get_batch_or_raise(db, batch_id)
        return self._batch_response(batch)

    def list_batches(self, db: Session, page: int, size: int, status: str | None = None) -> RecognitionBatchList:
        query = db.query(RecognitionBatch)
        if status is not None:
            query = query.filter(RecognitionBatch.status == status)
        total = query.count()
        batches = (
            query.options(selectinload(RecognitionBatch.items))
            .order_by(RecognitionBatch.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return RecognitionBatchList(
            items=[self._batch_response(batch) for batch in batches],
            total=total,
            page=page,
            size=size,
        )

    def list_batch_items(
        self,
        db: Session,
        batch_id: str,
        page: int,
        size: int,
        status: str | None = None,
    ) -> RecognitionBatchItemList:
        self._get_batch_or_raise(db, batch_id)
        query = db.query(RecognitionBatchItem).filter(RecognitionBatchItem.batch_id == batch_id)
        if status is not None:
            query = query.filter(RecognitionBatchItem.status == status)
        total = query.count()
        items = (
            query.options(joinedload(RecognitionBatchItem.image).joinedload(Image.annotation))
            .order_by(RecognitionBatchItem.id.asc())
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        responses = []
        for item in items:
            failure_category = self._failure_category(item.error)
            responses.append(
                RecognitionBatchItemResponse(
                    id=item.id,
                    image_id=item.image_id,
                    status=item.status,
                    error=item.error,
                    failure_category=failure_category,
                    failure_hint=self._failure_hint(failure_category),
                    image=RecognitionBatchItemImage(
                        id=item.image.id,
                        file_path=item.image.file_path,
                        caption=item.image.annotation.caption if item.image.annotation else "",
                        image_url=f"/api/images/{item.image.id}/file",
                    ),
                )
            )
        return RecognitionBatchItemList(
            items=responses,
            total=total,
            page=page,
            size=size,
        )

    def pause_batch(self, db: Session, batch_id: str) -> RecognitionBatch:
        batch = self._get_batch_or_raise(db, batch_id)
        if batch.status in {BATCH_STATUS_QUEUED, BATCH_STATUS_RUNNING}:
            batch.status = BATCH_STATUS_PAUSED
            batch.updated_at = utc_now()
            db.commit()
            db.refresh(batch)
        return batch

    def resume_batch(self, db: Session, batch_id: str) -> RecognitionBatch:
        batch = self._get_batch_or_raise(db, batch_id)
        if batch.status == BATCH_STATUS_PAUSED:
            batch.status = BATCH_STATUS_QUEUED
            batch.updated_at = utc_now()
            db.commit()
            db.refresh(batch)
        return batch

    def cancel_batch(self, db: Session, batch_id: str) -> RecognitionBatch:
        batch = self._get_batch_or_raise(db, batch_id)
        if batch.status not in TERMINAL_BATCH_STATUSES:
            batch.status = BATCH_STATUS_CANCELLED
            batch.completed_at = utc_now()
            for item in batch.items:
                if item.status == ITEM_STATUS_QUEUED:
                    item.status = ITEM_STATUS_CANCELLED
                    item.completed_at = utc_now()
            self._sync_batch_counters(batch)
            db.commit()
            db.refresh(batch)
        return batch

    def claim_next_items(self, db: Session, limit: int) -> list[RecognitionBatchItem]:
        batch = (
            db.query(RecognitionBatch)
            .filter(RecognitionBatch.status.in_([BATCH_STATUS_QUEUED, BATCH_STATUS_RUNNING]))
            .order_by(RecognitionBatch.created_at.asc())
            .first()
        )
        if batch is None:
            return []

        items = (
            db.query(RecognitionBatchItem)
            .filter(RecognitionBatchItem.batch_id == batch.id, RecognitionBatchItem.status == ITEM_STATUS_QUEUED)
            .order_by(RecognitionBatchItem.id.asc())
            .limit(limit)
            .all()
        )
        if not items:
            self.recalculate_batch(db, batch.id)
            return []

        now = utc_now()
        batch.status = BATCH_STATUS_RUNNING
        batch.started_at = batch.started_at or now
        for item in items:
            item.status = ITEM_STATUS_RUNNING
            item.started_at = now
            item.attempts += 1
        db.commit()
        for item in items:
            db.refresh(item)
        return items

    def process_item(self, item_id: int) -> None:
        db = self.session_factory()
        try:
            item = db.query(RecognitionBatchItem).filter(RecognitionBatchItem.id == item_id).first()
            if item is None:
                return
            batch_id = item.batch_id
            batch = self._get_batch_or_raise(db, batch_id)
            if batch.status == BATCH_STATUS_CANCELLED:
                item.status = ITEM_STATUS_CANCELLED
                item.completed_at = utc_now()
                db.commit()
                self.recalculate_batch(db, batch_id)
                return
            if batch.status == BATCH_STATUS_PAUSED:
                item.status = ITEM_STATUS_QUEUED
                item.started_at = None
                db.commit()
                return

            try:
                self.recognition_service.recognize_image(item.image_id, db)
            except Exception as exc:
                db.rollback()
                item = db.query(RecognitionBatchItem).filter(RecognitionBatchItem.id == item_id).first()
                if item is None:
                    return
                item.status = ITEM_STATUS_FAILED
                item.error = str(exc)
                item.completed_at = utc_now()
                logger.exception("Recognition failed while running batch", extra={"item_id": item_id})
            else:
                item.status = ITEM_STATUS_COMPLETED
                item.error = None
                item.completed_at = utc_now()
            db.commit()
            self.recalculate_batch(db, batch_id)
        finally:
            db.close()

    def recalculate_batch(self, db: Session, batch_id: str) -> RecognitionBatch:
        batch = self._get_batch_or_raise(db, batch_id)
        self._sync_batch_counters(batch)
        terminal_count = batch.completed + batch.failed + batch.cancelled
        if batch.status != BATCH_STATUS_CANCELLED and terminal_count == batch.total:
            batch.status = BATCH_STATUS_FAILED if batch.failed else BATCH_STATUS_COMPLETED
            batch.completed_at = utc_now()
        db.commit()
        db.refresh(batch)
        return batch

    def recover_interrupted_batches(self) -> None:
        db = self.session_factory()
        try:
            for item in db.query(RecognitionBatchItem).filter(RecognitionBatchItem.status == ITEM_STATUS_RUNNING).all():
                item.status = ITEM_STATUS_QUEUED
                item.started_at = None
            for batch in db.query(RecognitionBatch).filter(RecognitionBatch.status == BATCH_STATUS_RUNNING).all():
                batch.status = BATCH_STATUS_QUEUED
            db.commit()
        finally:
            db.close()

    def mark_item_failed(self, item_id: int, error: str) -> None:
        db = self.session_factory()
        try:
            item = db.query(RecognitionBatchItem).filter(RecognitionBatchItem.id == item_id).first()
            if item is None:
                return
            batch_id = item.batch_id
            item.status = ITEM_STATUS_FAILED
            item.error = error
            item.completed_at = utc_now()
            db.commit()
            self.recalculate_batch(db, batch_id)
        finally:
            db.close()

    def _get_batch_or_raise(self, db: Session, batch_id: str) -> RecognitionBatch:
        batch = db.query(RecognitionBatch).filter(RecognitionBatch.id == batch_id).first()
        if batch is None:
            raise BatchNotFoundError(f"Batch not found: {batch_id}")
        return batch

    def _batch_response(self, batch: RecognitionBatch) -> RecognitionBatchResponse:
        completed = sum(1 for item in batch.items if item.status == ITEM_STATUS_COMPLETED)
        failed = sum(1 for item in batch.items if item.status == ITEM_STATUS_FAILED)
        running = sum(1 for item in batch.items if item.status == ITEM_STATUS_RUNNING)
        cancelled = sum(1 for item in batch.items if item.status == ITEM_STATUS_CANCELLED)
        pending = sum(1 for item in batch.items if item.status == ITEM_STATUS_QUEUED)
        return RecognitionBatchResponse(
            batch_id=batch.id,
            total=batch.total,
            completed=completed,
            failed=failed,
            pending=pending,
            running=running,
            cancelled=cancelled,
            status=batch.status,
            created_at=self._as_utc(batch.created_at),
            updated_at=self._as_utc(batch.updated_at),
        )

    def _as_utc(self, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)

    def _failure_category(self, error: str | None) -> FailureCategory | None:
        if not error:
            return None
        error_text = error.lower()
        normalized_error = error_text.replace("_", " ").replace("-", "")
        if "provider" in error_text or "api key" in normalized_error or "apikey" in normalized_error or "configuration" in error_text:
            return "configuration"
        if "file" in error_text and ("missing" in error_text or "not found" in error_text):
            return "file_missing"
        if "no such file" in error_text:
            return "file_missing"
        if "model" in error_text or "recognition" in error_text:
            return "recognition_failed"
        return "unknown"

    def _failure_hint(self, category: FailureCategory | None) -> str | None:
        if category == "file_missing":
            return "文件路径失效，可以先修复文件路径或重新索引后再重试。"
        if category == "configuration":
            return "识别服务配置可能有问题，请检查模型提供方和密钥设置。"
        if category == "recognition_failed":
            return "模型识别失败，可以重试；如果反复失败，可能是图片内容或模型限制。"
        if category == "unknown":
            return "未知错误，可以重试；如果反复失败，请查看原始错误。"
        return None

    def _sync_batch_counters(self, batch: RecognitionBatch) -> None:
        batch.completed = sum(1 for item in batch.items if item.status == ITEM_STATUS_COMPLETED)
        batch.failed = sum(1 for item in batch.items if item.status == ITEM_STATUS_FAILED)
        batch.cancelled = sum(1 for item in batch.items if item.status == ITEM_STATUS_CANCELLED)
        batch.updated_at = utc_now()


class RecognitionBatchWorker:
    def __init__(
        self,
        service: BatchRecognitionService,
        session_factory: SessionFactory | sessionmaker[Session] = SessionLocal,
        *,
        chunk_size: int = 5,
        poll_interval: float = 1.0,
    ) -> None:
        self.service = service
        self.session_factory = session_factory
        self.chunk_size = chunk_size
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self.run, name="recognition-batch-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def run_once(self) -> None:
        db = self.session_factory()
        try:
            items = self.service.claim_next_items(db, self.chunk_size)
        except Exception:
            logger.exception("Recognition batch worker failed while claiming items")
            return
        finally:
            db.close()

        for item in items:
            if self._stop_event.is_set():
                break
            try:
                self.service.process_item(item.id)
            except Exception as exc:
                self.service.mark_item_failed(item.id, str(exc))
                logger.exception("Recognition batch worker failed while processing item", extra={"item_id": item.id})

    def run(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            if not self._stop_event.is_set():
                sleep(self.poll_interval)
