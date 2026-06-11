from pathlib import Path
from threading import Lock

from app.services.annotation import (
    ImageRecognitionInput,
    Recognizer,
    RecognitionResult,
)
from app.services.color_analysis import detect_dominant_color_label
from app.services.yolo_label_map import chinese_name_for_label


class YoloModelMissingError(Exception):
    """配置的 YOLO 模型文件不存在时抛出。"""


class YoloRuntimeError(Exception):
    """YOLO 推理过程异常时抛出。"""


class YoloRecognizer(Recognizer):
    def __init__(self, model_path: str | Path, confidence_threshold: float = 0.25) -> None:
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self._model = None
        self._lock = Lock()

    def _load_model(self) -> None:
        if not self.model_path.exists():
            raise YoloModelMissingError(
                f"YOLO model not found: {self.model_path}. "
                f"Set YOLO_MODEL_PATH in .env or switch RECOGNITION_PROVIDER back to mock."
            )
        # 延迟 import，避免 ultralytics 在导入期被强制加载
        from ultralytics import YOLO  # noqa: WPS433
        self._model = YOLO(str(self.model_path))

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is None:
                self._load_model()

    def recognize(self, image: ImageRecognitionInput) -> RecognitionResult:
        self._ensure_model()

        file_path = Path(image.file_path)
        try:
            results = self._model(str(file_path), verbose=False)
        except YoloModelMissingError:
            raise
        except Exception as exc:
            raise YoloRuntimeError(f"YOLO inference failed for {file_path}: {exc}") from exc

        tags_set: set[str] = {"本地图片"}
        if image.width > image.height:
            tags_set.add("landscape")
        elif image.height > image.width:
            tags_set.add("portrait")
        else:
            tags_set.add("square")

        if file_path.exists() and file_path.is_file():
            color_label = detect_dominant_color_label(file_path)
            if color_label is not None:
                tags_set.add(color_label)

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
                if confidence < self.confidence_threshold:
                    continue
                # bbox：YOLO 给的是归一化 (cx, cy, w, h)，转成左上角 (x, y) + 宽高
                cx, cy, bw, bh = (float(v) for v in box.xywhn[0].tolist())
                x = max(0.0, cx - bw / 2)
                y = max(0.0, cy - bh / 2)
                name = chinese_name_for_label(label)
                tags_set.add(name)
                objects.append({
                    "label": label,
                    "name": name,
                    "confidence": confidence,
                    "x": round(x, 4),
                    "y": round(y, 4),
                    "w": round(bw, 4),
                    "h": round(bh, 4),
                })

        objects.sort(key=lambda obj: obj["confidence"], reverse=True)
        objects = objects[:20]

        return RecognitionResult(
            caption="本地图片",
            tags=sorted(tags_set),
            objects=objects,
            model_used="yolo11n",
        )
