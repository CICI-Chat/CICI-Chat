"""实时摄像头 YOLO 多目标追踪。"""

from pathlib import Path
from threading import Lock

from app.services.yolo_label_map import chinese_name_for_label


class YoloTrackerRuntimeError(Exception):
    """YOLO tracker 运行失败时抛出。"""


class YoloTracker:
    def __init__(self, model_path: str | Path, confidence_threshold: float = 0.25) -> None:
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._lock = Lock()

    def _load_model(self) -> None:
        if not self.model_path.exists():
            raise FileNotFoundError(f"YOLO model not found: {self.model_path}")
        from ultralytics import YOLO  # noqa: WPS433
        self._model = YOLO(str(self.model_path))

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is None:
                self._load_model()

    def track_frame(self, frame) -> list[dict]:
        self._ensure_model()
        try:
            results = self._model.track(frame, persist=True, verbose=False)
        except Exception as exc:
            raise YoloTrackerRuntimeError(f"YOLO tracking failed: {exc}") from exc
        return track_results_to_objects(results, self.confidence_threshold)


def _track_id_from_box(box) -> int | None:
    track_id = getattr(box, "id", None)
    if track_id is None:
        return None
    try:
        return int(track_id[0].item())
    except (TypeError, IndexError, AttributeError, ValueError):
        return None


def track_results_to_objects(results, confidence_threshold: float) -> list[dict]:
    objects: list[dict] = []
    for result in results:
        boxes = getattr(result, "boxes", None)
        if not boxes:
            continue
        names = getattr(result, "names", {})
        for box in boxes:
            label_idx = int(box.cls[0].item())
            label = names.get(label_idx, str(label_idx))
            confidence = round(float(box.conf[0].item()), 4)
            if confidence < confidence_threshold:
                continue
            cx, cy, bw, bh = (float(v) for v in box.xywhn[0].tolist())
            x = max(0.0, cx - bw / 2)
            y = max(0.0, cy - bh / 2)
            obj = {
                "label": label,
                "name": chinese_name_for_label(label),
                "confidence": confidence,
                "x": round(x, 4),
                "y": round(y, 4),
                "w": round(bw, 4),
                "h": round(bh, 4),
            }
            track_id = _track_id_from_box(box)
            if track_id is not None:
                obj["track_id"] = track_id
            objects.append(obj)
    objects.sort(key=lambda item: item["confidence"], reverse=True)
    return objects[:20]
