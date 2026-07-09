"""基于 bbox 估算物体距离（小孔成像模型）。

D = (真实尺寸 * f_px) / 像素尺寸

- person 用肩宽测距（近距离全身超画面，肩宽仍在画面内，更鲁棒）
- 其他物体用高度测距
"""

FOCAL_LENGTH_PX: int | None = None
"""当前有效焦距。首次引用时从 data/calibration.json 加载。"""


def _get_focal_length() -> int:
    global FOCAL_LENGTH_PX
    if FOCAL_LENGTH_PX is None:
        from app.services.calibration import load_focal_length
        FOCAL_LENGTH_PX = load_focal_length()
    return FOCAL_LENGTH_PX

KNOWN_HEIGHTS: dict[str, float] = {
    "person": 1.70,
    "bicycle": 1.00,
    "car": 1.50,
    "motorcycle": 1.20,
    "bus": 3.50,
    "truck": 3.00,
    "dog": 0.50,
    "cat": 0.30,
    "bird": 0.15,
    "horse": 1.50,
    "sheep": 0.80,
    "cow": 1.40,
    "elephant": 2.50,
    "bear": 1.50,
    "zebra": 1.40,
    "giraffe": 4.50,
}
"""COCO 危险标签的平均高度（米）。
只对 DANGER_LABELS 中的标签定义高度。
"""

# 用宽度测距的标签及其真实宽度（米）。
# person 用肩宽而非身高：近距离全身超出画面，但肩宽仍在画面内，测距更鲁棒。
KNOWN_WIDTHS: dict[str, float] = {
    "person": 0.45,   # 成人肩宽
}


def estimate_distance(
    label: str,
    h_norm: float,
    frame_height: int,
    w_norm: float | None = None,
    frame_width: int | None = None,
) -> float | None:
    """估算目标距摄像头的大致距离。

    优先用宽度测距（对 person 更鲁棒，近距离肩宽不超出画面）；
    否则回退到高度测距。

    Args:
        label: COCO 标签名。
        h_norm: bbox 归一化高度（0~1）。
        frame_height: 画面像素高度。
        w_norm: bbox 归一化宽度（0~1），用于宽度测距。
        frame_width: 画面像素宽度。

    Returns:
        float: 距离（米），或 None（无法估算）。
    """
    # 宽度测距（优先，适合 person）
    if (
        label in KNOWN_WIDTHS
        and w_norm is not None
        and frame_width is not None
    ):
        w_px = w_norm * frame_width
        if w_px > 0:
            return (KNOWN_WIDTHS[label] * _get_focal_length()) / w_px

    # 高度测距（回退）
    if label not in KNOWN_HEIGHTS:
        return None

    real_height = KNOWN_HEIGHTS[label]
    h_px = h_norm * frame_height
    if h_px <= 0:
        return None

    return (real_height * _get_focal_length()) / h_px
