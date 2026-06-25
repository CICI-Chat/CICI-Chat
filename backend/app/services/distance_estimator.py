"""基于 bbox 高度估算物体距离（小孔成像模型）。

D = (H_real * f_px) / h_px

h_px = h_norm * frame_height
D    = (KNOWN_HEIGHTS[label] * FOCAL_LENGTH_PX) / h_px
"""

FOCAL_LENGTH_PX = 700
"""默认焦距（像素单位），适配 640x480 下的典型笔记本摄像头。
后续可通过标定工具校准并保存到 data/calibration.json。
"""

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


def estimate_distance(label: str, h_norm: float, frame_height: int) -> float | None:
    """估算目标距摄像头的大致距离。

    Args:
        label: COCO 标签名。
        h_norm: bbox 归一化高度（0~1）。
        frame_height: 画面像素高度。

    Returns:
        float: 距离（米），或 None（无法估算）。
    """
    if label not in KNOWN_HEIGHTS:
        return None

    real_height = KNOWN_HEIGHTS[label]
    h_px = h_norm * frame_height

    if h_px <= 0:
        return None

    return (real_height * FOCAL_LENGTH_PX) / h_px
