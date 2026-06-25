"""焦距标定：保存/加载到 data/calibration.json，默认值 700。"""
import json
from datetime import datetime, timezone
from pathlib import Path

CALIBRATION_PATH = Path("./data/calibration.json")
DEFAULT_FOCAL_LENGTH = 700


def load_focal_length() -> int:
    if not CALIBRATION_PATH.exists():
        return DEFAULT_FOCAL_LENGTH
    try:
        with open(CALIBRATION_PATH) as f:
            data = json.load(f)
        return int(data.get("focal_length_px", DEFAULT_FOCAL_LENGTH))
    except (json.JSONDecodeError, OSError, ValueError):
        return DEFAULT_FOCAL_LENGTH


def save_focal_length(focal_length_px: int) -> None:
    CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CALIBRATION_PATH, "w") as f:
        json.dump({
            "focal_length_px": focal_length_px,
            "calibrated_at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)


def compute_focal_length(distance_m: float, h_norm: float, frame_height: int, known_height_m: float = 1.7) -> int:
    """从已知距离和 bbox 高度反算焦距。"""
    h_px = h_norm * frame_height
    if h_px <= 0:
        raise ValueError("bbox 高度为 0，无法标定")
    return round((distance_m * h_px) / known_height_m)
