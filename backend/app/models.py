from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Image(Base):
    __tablename__ = "images"
    __table_args__ = (UniqueConstraint("file_hash", name="uq_images_file_hash"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    annotation: Mapped["Annotation"] = relationship(back_populates="image", uselist=False, cascade="all, delete-orphan")


class Annotation(Base):
    __tablename__ = "annotations"

    image_id: Mapped[str] = mapped_column(ForeignKey("images.id"), primary_key=True)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str] = mapped_column(Text, nullable=False)
    objects: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    model_used: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    image: Mapped[Image] = relationship(back_populates="annotation")


class RecognitionBatch(Base):
    __tablename__ = "recognition_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancelled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    items: Mapped[list["RecognitionBatchItem"]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class RecognitionBatchItem(Base):
    __tablename__ = "recognition_batch_items"
    __table_args__ = (UniqueConstraint("batch_id", "image_id", name="uq_recognition_batch_item_image"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("recognition_batches.id"), nullable=False)
    image_id: Mapped[str] = mapped_column(ForeignKey("images.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    batch: Mapped[RecognitionBatch] = relationship(back_populates="items")
    image: Mapped[Image] = relationship()
