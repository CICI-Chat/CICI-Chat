from pathlib import Path

from PIL import Image as PillowImage
from PIL import UnidentifiedImageError

COLOR_PALETTE: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("黑色", (0, 0, 0)),
    ("白色", (255, 255, 255)),
    ("灰色", (128, 128, 128)),
    ("红色", (220, 20, 60)),
    ("橙色", (255, 140, 0)),
    ("黄色", (255, 215, 0)),
    ("绿色", (34, 139, 34)),
    ("蓝色", (30, 144, 255)),
    ("紫色", (128, 0, 128)),
    ("粉色", (255, 105, 180)),
    ("棕色", (139, 69, 19)),
)


def detect_dominant_color_label(file_path: str | Path) -> str | None:
    try:
        with PillowImage.open(file_path) as image:
            rgb_image = image.convert("RGB")
            rgb_image.thumbnail((64, 64))
            colors = rgb_image.getcolors(maxcolors=64 * 64)
    except (OSError, UnidentifiedImageError):
        return None

    if not colors:
        return None

    _count, dominant = max(colors, key=lambda item: item[0])
    return closest_color_label(dominant)


def closest_color_label(rgb: tuple[int, int, int]) -> str:
    return min(COLOR_PALETTE, key=lambda color: color_distance(rgb, color[1]))[0]


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return sum((left[index] - right[index]) ** 2 for index in range(3))
