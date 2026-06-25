def test_estimate_distance_person():
    from app.services.distance_estimator import estimate_distance, KNOWN_HEIGHTS, FOCAL_LENGTH_PX

    # person: 1.7m, h=0.6, frame_height=480 -> h_px=288
    # distance = (1.7 * 700) / 288 = 4.13
    d = estimate_distance(label="person", h_norm=0.6, frame_height=480)
    assert d is not None
    assert round(d, 1) == 4.1


def test_estimate_distance_zero_bbox_returns_none():
    from app.services.distance_estimator import estimate_distance

    d = estimate_distance(label="person", h_norm=0.0, frame_height=480)
    assert d is None


def test_estimate_distance_non_danger_returns_none():
    from app.services.distance_estimator import estimate_distance

    d = estimate_distance(label="chair", h_norm=0.5, frame_height=480)
    assert d is None


def test_estimate_distance_different_labels_have_different_heights():
    from app.services.distance_estimator import KNOWN_HEIGHTS

    assert KNOWN_HEIGHTS["person"] == 1.70
    assert KNOWN_HEIGHTS["car"] == 1.50
    assert KNOWN_HEIGHTS["dog"] == 0.50
    assert "chair" not in KNOWN_HEIGHTS
    assert "book" not in KNOWN_HEIGHTS
