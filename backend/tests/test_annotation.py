from app.services.annotation import create_mock_annotation


def test_create_mock_annotation_returns_phase_one_values():
    annotation = create_mock_annotation()

    assert annotation.caption == "待分析的本地图片"
    assert annotation.tags == ["本地图片", "待分析"]
    assert annotation.objects == []
    assert annotation.model_used == "mock"
