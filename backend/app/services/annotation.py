from dataclasses import dataclass


@dataclass(frozen=True)
class MockAnnotation:
    caption: str
    tags: list[str]
    objects: list[dict[str, object]]
    model_used: str


def create_mock_annotation() -> MockAnnotation:
    return MockAnnotation(
        caption="待分析的本地图片",
        tags=["本地图片", "待分析"],
        objects=[],
        model_used="mock",
    )
