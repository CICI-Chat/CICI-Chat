from datetime import UTC, datetime

import pytest

from app.models import Image, RecognitionBatch, RecognitionBatchItem
from app.services.batch_recognition import (
    BatchNotFoundError,
    BatchRecognitionService,
    EmptyBatchError,
    RecognitionBatchWorker,
)


class FakeRecognitionService:
    def __init__(
        self,
        failing_ids: set[str] | None = None,
        cancel_ids: set[str] | None = None,
        pause_ids: set[str] | None = None,
    ) -> None:
        self.failing_ids = failing_ids or set()
        self.cancel_ids = cancel_ids or set()
        self.pause_ids = pause_ids or set()
        self.calls: list[tuple[str, object]] = []

    def recognize_image(self, image_id: str, db: object) -> object:
        self.calls.append((image_id, db))
        if image_id in self.cancel_ids or image_id in self.pause_ids:
            batch_item = db.query(RecognitionBatchItem).filter_by(image_id=image_id).one()
            batch = db.query(RecognitionBatch).filter_by(id=batch_item.batch_id).one()
            batch.status = "cancelled" if image_id in self.cancel_ids else "paused"
            db.commit()
        if image_id in self.failing_ids:
            raise RuntimeError(f"recognition failed for {image_id}")
        return object()


class FakeSession:
    def close(self) -> None:
        pass


class FailingClaimService(BatchRecognitionService):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def claim_next_items(self, db, limit: int):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary claim failure")
        return []


class FailingProcessService(BatchRecognitionService):
    def process_item(self, item_id: int) -> None:
        raise RuntimeError(f"unexpected failure for {item_id}")


def add_image(db_session, image_id: str) -> Image:
    now = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)
    image = Image(
        id=image_id,
        file_path=f"/tmp/{image_id}.png",
        file_hash=f"hash-{image_id}",
        file_size=100,
        width=32,
        height=24,
        format="PNG",
        created_at=now,
        modified_at=now,
        indexed_at=now,
    )
    db_session.add(image)
    db_session.commit()
    return image


def test_create_batch_persists_queued_batch_with_items(db_session):
    add_image(db_session, "image-1")
    add_image(db_session, "image-2")
    service = BatchRecognitionService()

    batch = service.create_batch(db_session, ["image-1", "image-2"])

    saved = db_session.query(RecognitionBatch).filter_by(id=batch.id).one()
    assert saved.status == "queued"
    assert saved.total == 2
    assert saved.completed == 0
    assert saved.failed == 0
    assert saved.cancelled == 0
    assert [item.image_id for item in saved.items] == ["image-1", "image-2"]
    assert all(item.status == "queued" for item in saved.items)


def test_create_batch_raises_for_empty_image_ids(db_session):
    service = BatchRecognitionService()

    with pytest.raises(EmptyBatchError):
        service.create_batch(db_session, [])


def test_create_batch_deduplicates_image_ids_preserving_order(db_session):
    add_image(db_session, "image-1")
    add_image(db_session, "image-2")
    service = BatchRecognitionService()

    batch = service.create_batch(db_session, ["image-1", "image-2", "image-1"])

    saved = db_session.query(RecognitionBatch).filter_by(id=batch.id).one()
    assert saved.total == 2
    assert [item.image_id for item in saved.items] == ["image-1", "image-2"]


def test_get_batch_progress_counts_item_statuses(db_session):
    for image_id in ["image-1", "image-2", "image-3", "image-4", "image-5"]:
        add_image(db_session, image_id)
    batch = RecognitionBatch(id="batch-progress", status="running", total=5)
    batch.items = [
        RecognitionBatchItem(image_id="image-1", status="completed"),
        RecognitionBatchItem(image_id="image-2", status="failed"),
        RecognitionBatchItem(image_id="image-3", status="running"),
        RecognitionBatchItem(image_id="image-4", status="queued"),
        RecognitionBatchItem(image_id="image-5", status="cancelled"),
    ]
    db_session.add(batch)
    db_session.commit()

    progress = BatchRecognitionService().get_batch_progress(db_session, "batch-progress")

    assert progress.batch_id == "batch-progress"
    assert progress.total == 5
    assert progress.completed == 1
    assert progress.failed == 1
    assert progress.running == 1
    assert progress.pending == 1
    assert progress.cancelled == 1
    assert progress.status == "running"


def test_get_batch_progress_raises_for_missing_batch_id(db_session):
    service = BatchRecognitionService()

    with pytest.raises(BatchNotFoundError, match="missing-batch"):
        service.get_batch_progress(db_session, "missing-batch")


def test_pause_batch_prevents_claiming_items(db_session):
    add_image(db_session, "image-1")
    service = BatchRecognitionService()
    batch = service.create_batch(db_session, ["image-1"])

    service.pause_batch(db_session, batch.id)
    claimed = service.claim_next_items(db_session, limit=1)

    assert claimed == []
    assert service.get_batch_progress(db_session, batch.id).status == "paused"


def test_resume_batch_makes_paused_items_claimable(db_session):
    add_image(db_session, "image-1")
    service = BatchRecognitionService()
    batch = service.create_batch(db_session, ["image-1"])
    service.pause_batch(db_session, batch.id)

    service.resume_batch(db_session, batch.id)
    claimed = service.claim_next_items(db_session, limit=1)

    assert [item.image_id for item in claimed] == ["image-1"]
    assert service.get_batch_progress(db_session, batch.id).status == "running"


def test_cancel_batch_marks_queued_items_cancelled(db_session):
    add_image(db_session, "image-1")
    add_image(db_session, "image-2")
    service = BatchRecognitionService()
    batch = service.create_batch(db_session, ["image-1", "image-2"])

    service.cancel_batch(db_session, batch.id)

    progress = service.get_batch_progress(db_session, batch.id)
    assert progress.status == "cancelled"
    assert progress.cancelled == 2
    assert progress.pending == 0


def test_claim_next_items_marks_batch_and_items_running(db_session):
    for image_id in ["image-1", "image-2", "image-3"]:
        add_image(db_session, image_id)
    service = BatchRecognitionService()
    batch = service.create_batch(db_session, ["image-1", "image-2", "image-3"])

    claimed = service.claim_next_items(db_session, limit=2)

    assert [item.image_id for item in claimed] == ["image-1", "image-2"]
    assert all(item.status == "running" for item in claimed)
    progress = service.get_batch_progress(db_session, batch.id)
    assert progress.status == "running"
    assert progress.running == 2
    assert progress.pending == 1


def test_process_item_marks_item_completed(db_session, tmp_path):
    add_image(db_session, "image-1")
    service = BatchRecognitionService(session_factory=lambda: db_session, recognition_service=FakeRecognitionService())
    batch = service.create_batch(db_session, ["image-1"])
    item = service.claim_next_items(db_session, limit=1)[0]

    service.process_item(item.id)

    progress = service.get_batch_progress(db_session, batch.id)
    assert progress.completed == 1
    assert progress.pending == 0
    assert progress.running == 0
    assert progress.status == "completed"


def test_process_item_keeps_completed_item_if_batch_cancelled_during_recognition(db_session):
    add_image(db_session, "image-1")
    service = BatchRecognitionService(
        session_factory=lambda: db_session,
        recognition_service=FakeRecognitionService(cancel_ids={"image-1"}),
    )
    batch = service.create_batch(db_session, ["image-1"])
    item = service.claim_next_items(db_session, limit=1)[0]
    item_id = item.id

    service.process_item(item_id)

    progress = service.get_batch_progress(db_session, batch.id)
    saved_item = db_session.query(RecognitionBatchItem).filter_by(id=item_id).one()
    assert saved_item.status == "completed"
    assert progress.completed == 1
    assert progress.cancelled == 0
    assert progress.status == "cancelled"


def test_process_item_keeps_completed_item_if_batch_paused_during_recognition(db_session):
    add_image(db_session, "image-1")
    service = BatchRecognitionService(
        session_factory=lambda: db_session,
        recognition_service=FakeRecognitionService(pause_ids={"image-1"}),
    )
    batch = service.create_batch(db_session, ["image-1"])
    item = service.claim_next_items(db_session, limit=1)[0]
    item_id = item.id

    service.process_item(item_id)

    progress = service.get_batch_progress(db_session, batch.id)
    saved_item = db_session.query(RecognitionBatchItem).filter_by(id=item_id).one()
    assert saved_item.status == "completed"
    assert progress.completed == 1
    assert progress.pending == 0
    assert progress.status == "completed"


def test_process_item_requeues_item_if_batch_paused_before_recognition(db_session):
    add_image(db_session, "image-1")
    service = BatchRecognitionService(session_factory=lambda: db_session, recognition_service=FakeRecognitionService())
    batch = service.create_batch(db_session, ["image-1"])
    batch_id = batch.id
    item = service.claim_next_items(db_session, limit=1)[0]
    item_id = item.id
    service.pause_batch(db_session, batch_id)

    service.process_item(item_id)

    progress = service.get_batch_progress(db_session, batch_id)
    saved_item = db_session.query(RecognitionBatchItem).filter_by(id=item_id).one()
    assert saved_item.status == "queued"
    assert progress.pending == 1
    assert progress.running == 0
    assert progress.status == "paused"


def test_worker_continues_after_claim_exception():
    service = FailingClaimService()
    worker = RecognitionBatchWorker(service, session_factory=FakeSession, poll_interval=0)

    worker.run_once()
    worker.run_once()

    assert service.calls == 2


def test_worker_marks_item_failed_when_processing_raises(db_session):
    add_image(db_session, "image-1")
    service = FailingProcessService(session_factory=lambda: db_session)
    batch = service.create_batch(db_session, ["image-1"])
    batch_id = batch.id
    worker = RecognitionBatchWorker(service, session_factory=lambda: db_session, poll_interval=0)

    worker.run_once()

    progress = service.get_batch_progress(db_session, batch_id)
    saved_item = db_session.query(RecognitionBatchItem).filter_by(batch_id=batch_id).one()
    assert saved_item.status == "failed"
    assert "unexpected failure" in saved_item.error
    assert progress.failed == 1
    assert progress.running == 0


def test_process_item_marks_item_failed_when_recognition_raises(db_session):
    add_image(db_session, "image-1")
    recognition_service = FakeRecognitionService(failing_ids={"image-1"})
    service = BatchRecognitionService(session_factory=lambda: db_session, recognition_service=recognition_service)
    batch = service.create_batch(db_session, ["image-1"])
    item = service.claim_next_items(db_session, limit=1)[0]
    item_id = item.id

    service.process_item(item_id)

    progress = service.get_batch_progress(db_session, batch.id)
    saved_item = db_session.query(RecognitionBatchItem).filter_by(id=item_id).one()
    assert progress.failed == 1
    assert progress.status == "failed"
    assert "recognition failed for image-1" in saved_item.error


def test_recover_interrupted_batches_requeues_running_work(db_session):
    add_image(db_session, "image-1")
    batch = RecognitionBatch(id="batch-recover", status="running", total=1)
    batch.items = [RecognitionBatchItem(image_id="image-1", status="running")]
    db_session.add(batch)
    db_session.commit()
    service = BatchRecognitionService(session_factory=lambda: db_session)

    service.recover_interrupted_batches()

    progress = service.get_batch_progress(db_session, "batch-recover")
    saved_item = db_session.query(RecognitionBatchItem).filter_by(batch_id="batch-recover").one()
    assert progress.status == "queued"
    assert saved_item.status == "queued"


def test_recover_interrupted_batches_keeps_paused_batches_paused(db_session):
    add_image(db_session, "image-1")
    batch = RecognitionBatch(id="batch-paused", status="paused", total=1)
    batch.items = [RecognitionBatchItem(image_id="image-1", status="queued")]
    db_session.add(batch)
    db_session.commit()
    service = BatchRecognitionService(session_factory=lambda: db_session)

    service.recover_interrupted_batches()

    assert service.get_batch_progress(db_session, "batch-paused").status == "paused"


def test_list_batches_returns_newest_first_with_pagination(db_session):
    for image_id in ["image-1", "image-2", "image-3"]:
        add_image(db_session, image_id)
    older = RecognitionBatch(
        id="batch-older",
        status="completed",
        total=1,
        created_at=datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 5, 12, 0, tzinfo=UTC),
    )
    middle = RecognitionBatch(
        id="batch-middle",
        status="failed",
        total=1,
        created_at=datetime(2026, 6, 6, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 6, 12, 0, tzinfo=UTC),
    )
    newer = RecognitionBatch(
        id="batch-newer",
        status="running",
        total=1,
        created_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
    )
    older.items = [RecognitionBatchItem(image_id="image-1", status="completed")]
    middle.items = [RecognitionBatchItem(image_id="image-2", status="failed", error="boom")]
    newer.items = [RecognitionBatchItem(image_id="image-3", status="running")]
    db_session.add_all([older, middle, newer])
    db_session.commit()

    result = BatchRecognitionService().list_batches(db_session, page=1, size=2)

    assert result.total == 3
    assert result.page == 1
    assert result.size == 2
    assert [batch.batch_id for batch in result.items] == ["batch-newer", "batch-middle"]
    assert result.items[0].created_at == datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
    assert result.items[0].updated_at == datetime(2026, 6, 7, 12, 0, tzinfo=UTC)


def test_list_batches_filters_by_status(db_session):
    add_image(db_session, "image-running")
    add_image(db_session, "image-failed")
    running = RecognitionBatch(id="batch-running", status="running", total=1, created_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC))
    failed = RecognitionBatch(id="batch-failed", status="failed", total=1, created_at=datetime(2026, 6, 8, 12, 0, tzinfo=UTC))
    running.items = [RecognitionBatchItem(image_id="image-running", status="running")]
    failed.items = [RecognitionBatchItem(image_id="image-failed", status="failed")]
    db_session.add_all([running, failed])
    db_session.commit()

    result = BatchRecognitionService().list_batches(db_session, page=1, size=20, status="failed")

    assert result.total == 1
    assert [batch.batch_id for batch in result.items] == ["batch-failed"]


def test_list_batch_items_filters_failed_and_includes_image_details(db_session):
    add_image(db_session, "image-failed")
    add_image(db_session, "image-completed")
    batch = RecognitionBatch(id="batch-items", status="failed", total=2)
    failed_item = RecognitionBatchItem(image_id="image-failed", status="failed", error="missing file")
    batch.items = [
        failed_item,
        RecognitionBatchItem(image_id="image-completed", status="completed"),
    ]
    db_session.add(batch)
    db_session.commit()

    result = BatchRecognitionService().list_batch_items(db_session, "batch-items", page=1, size=50, status="failed")

    assert result.total == 1
    assert result.page == 1
    assert result.size == 50
    assert len(result.items) == 1
    item = result.items[0]
    assert item.id == failed_item.id
    assert item.image_id == "image-failed"
    assert item.status == "failed"
    assert item.error == "missing file"
    assert item.failure_category == "file_missing"
    assert "修复文件路径" in item.failure_hint
    assert item.image.id == "image-failed"
    assert item.image.file_path == "/tmp/image-failed.png"
    assert item.image.caption == ""
    assert item.image.image_url == "/api/images/image-failed/file"


def test_list_batch_items_classifies_missing_api_key_as_configuration(db_session):
    add_image(db_session, "image-config-failed")
    batch = RecognitionBatch(id="batch-config-failed", status="failed", total=1)
    batch.items = [RecognitionBatchItem(image_id="image-config-failed", status="failed", error="missing API key")]
    db_session.add(batch)
    db_session.commit()

    result = BatchRecognitionService().list_batch_items(db_session, "batch-config-failed", page=1, size=50, status="failed")

    item = result.items[0]
    assert item.failure_category == "configuration"
    assert "密钥" in item.failure_hint


def test_list_batch_items_raises_for_missing_batch(db_session):
    with pytest.raises(BatchNotFoundError, match="missing-batch"):
        BatchRecognitionService().list_batch_items(db_session, "missing-batch", page=1, size=50, status="failed")
