from pathlib import Path

from PIL import Image as PillowImage
from PIL import UnidentifiedImageError

COLOR_PALETTE: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("黑色", (0, 0, 0)),
    ("白色", (255, 255, 255)),
    ("浅灰色", (229, 231, 235)),
    ("灰色", (128, 128, 128)),
    ("深灰色", (31, 41, 55)),
    ("浅红色", (254, 202, 202)),
    ("红色", (220, 20, 60)),
    ("深红色", (127, 29, 29)),
    ("浅橙色", (254, 215, 170)),
    ("橙色", (255, 140, 0)),
    ("深橙色", (124, 45, 18)),
    ("浅黄色", (254, 249, 195)),
    ("黄色", (255, 215, 0)),
    ("深黄色", (113, 63, 18)),
    ("浅绿色", (187, 247, 208)),
    ("绿色", (34, 139, 34)),
    ("深绿色", (20, 83, 45)),
    ("浅青色", (207, 250, 254)),
    ("青色", (6, 182, 212)),
    ("深青色", (21, 94, 117)),
    ("浅蓝色", (191, 219, 254)),
    ("蓝色", (30, 144, 255)),
    ("深蓝色", (30, 58, 138)),
    ("浅紫色", (233, 213, 255)),
    ("紫色", (128, 0, 128)),
    ("深紫色", (88, 28, 135)),
    ("浅粉色", (252, 231, 243)),
    ("粉色", (255, 105, 180)),
    ("深粉色", (131, 24, 67)),
    ("浅棕色", (231, 209, 185)),
    ("棕色", (139, 69, 19)),
    ("深棕色", (67, 36, 17)),
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
    red, green, blue = rgb
    if min(rgb) >= 240 and max(rgb) - min(rgb) <= 15:
        return "白色"
    if green >= 240 and green - max(red, blue) >= 25:
        return "浅绿色"

    return min(COLOR_PALETTE, key=lambda color: color_distance(rgb, color[1]))[0]


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return sum((left[index] - right[index]) ** 2 for index in range(3))
