class FakeScalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class FakeVector:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class FakeBox:
    def __init__(self, *, cls_id=0, conf=0.9, xywhn=(0.5, 0.5, 0.2, 0.4), track_id=7):
        self.cls = [FakeScalar(cls_id)]
        self.conf = [FakeScalar(conf)]
        self.xywhn = [FakeVector(list(xywhn))]
        self.id = None if track_id is None else [FakeScalar(track_id)]


class FakeResult:
    def __init__(self, boxes, names=None):
        self.boxes = boxes
        self.names = names or {0: "person", 1: "chair"}


def test_track_results_to_objects_includes_track_id_and_bbox():
    from app.services.yolo_tracker import track_results_to_objects

    objects = track_results_to_objects(
        [FakeResult([FakeBox(cls_id=0, conf=0.91, xywhn=(0.4, 0.5, 0.2, 0.6), track_id=3)])],
        confidence_threshold=0.25,
    )

    assert objects == [{
        "track_id": 3,
        "label": "person",
        "name": "人",
        "confidence": 0.91,
        "x": 0.3,
        "y": 0.2,
        "w": 0.2,
        "h": 0.6,
    }]


def test_track_results_to_objects_keeps_box_without_track_id():
    from app.services.yolo_tracker import track_results_to_objects

    objects = track_results_to_objects(
        [FakeResult([FakeBox(cls_id=0, conf=0.91, track_id=None)])],
        confidence_threshold=0.25,
    )

    assert "track_id" not in objects[0]
    assert objects[0]["label"] == "person"


def test_track_results_to_objects_filters_low_confidence():
    from app.services.yolo_tracker import track_results_to_objects

    objects = track_results_to_objects(
        [FakeResult([FakeBox(cls_id=0, conf=0.1, track_id=1)])],
        confidence_threshold=0.25,
    )

    assert objects == []
