import app.services.distance_estimator as de


def _set_focal(value):
    """测试用：直接设定焦距，绕过标定文件依赖。"""
    de.FOCAL_LENGTH_PX = value


def test_estimate_distance_by_height_fallback():
    # 不传宽度 -> 回退高度测距
    # person: 1.7m, h_norm=0.6, frame_height=480 -> h_px=288
    # distance = (1.7 * 700) / 288 = 4.13
    _set_focal(700)
    d = de.estimate_distance(label="person", h_norm=0.6, frame_height=480)
    assert d is not None
    assert round(d, 1) == 4.1


def test_estimate_distance_by_width_for_person():
    # person 传了宽度 -> 优先用肩宽测距
    # 肩宽 0.45m, w_norm=0.3, frame_width=320 -> w_px=96
    # distance = (0.45 * 700) / 96 = 3.28
    _set_focal(700)
    d = de.estimate_distance(
        label="person", h_norm=0.6, frame_height=480,
        w_norm=0.3, frame_width=320,
    )
    assert d is not None
    assert round(d, 1) == 3.3


def test_estimate_distance_zero_bbox_returns_none():
    _set_focal(700)
    d = de.estimate_distance(label="person", h_norm=0.0, frame_height=480)
    assert d is None


def test_estimate_distance_non_danger_returns_none():
    _set_focal(700)
    d = de.estimate_distance(label="chair", h_norm=0.5, frame_height=480)
    assert d is None


def test_known_tables():
    assert de.KNOWN_HEIGHTS["person"] == 1.70
    assert de.KNOWN_HEIGHTS["car"] == 1.50
    assert de.KNOWN_WIDTHS["person"] == 0.45
    assert "chair" not in de.KNOWN_HEIGHTS
