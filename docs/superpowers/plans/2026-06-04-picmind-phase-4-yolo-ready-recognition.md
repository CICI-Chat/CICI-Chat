# PicMind Phase 4 YOLO 前置识别实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 增加本地主色识别，把颜色标签写入现有识别结果，并为后续 YOLO 物体检测结果结构预留清晰边界。

**架构：** 新增一个专注的颜色分析服务，使用 Pillow 从图片像素计算主色并映射为中文颜色标签。`MockRecognizer` 保持现有识别器接口，在基础标签和方向标签之外加入颜色标签；后端搜索继续通过现有 `Annotation.tags` 命中颜色关键词。

**技术栈：** Python 3.11、FastAPI、SQLAlchemy、Pillow、pytest、React/Vite/TypeScript。

---

## 文件结构

- 创建：`backend/app/services/color_analysis.py`
  - 职责：读取图片主色并返回中文颜色标签，不处理数据库、不处理 API。
- 修改：`backend/app/services/annotation.py`
  - 职责：让 `MockRecognizer` 调用颜色分析服务，把颜色标签加入 `RecognitionResult.tags`。
- 修改：`backend/tests/test_recognition.py`
  - 职责：覆盖 MockRecognizer 颜色标签、RecognitionService 持久化颜色标签、识别后不保留 `待分析`。
- 修改：`backend/tests/test_api.py`
  - 职责：覆盖 `/api/images?q=黄色` 能通过 tags 搜到已识别黄色图片。

## 任务 1：增加颜色分析服务

**文件：**
- 创建：`backend/app/services/color_analysis.py`
- 测试：`backend/tests/test_recognition.py`

- [ ] **步骤 1：编写失败的测试**

在 `backend/tests/test_recognition.py` 增加导入：

```python
from PIL import Image as PillowImage
from app.services.color_analysis import detect_dominant_color_label
```

在文件末尾增加测试：

```python
def test_detect_dominant_color_label_identifies_red(tmp_path):
    path = tmp_path / "red.png"
    PillowImage.new("RGB", (20, 20), color=(255, 0, 0)).save(path)

    assert detect_dominant_color_label(path) == "红色"


def test_detect_dominant_color_label_identifies_yellow(tmp_path):
    path = tmp_path / "yellow.png"
    PillowImage.new("RGB", (20, 20), color=(255, 230, 0)).save(path)

    assert detect_dominant_color_label(path) == "黄色"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_recognition.py::test_detect_dominant_color_label_identifies_red tests/test_recognition.py::test_detect_dominant_color_label_identifies_yellow -q
```

预期：FAIL，报错包含：

```text
ModuleNotFoundError: No module named 'app.services.color_analysis'
```

- [ ] **步骤 3：编写最少实现代码**

创建 `backend/app/services/color_analysis.py`：

```python
from pathlib import Path

from PIL import Image as PillowImage

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
    with PillowImage.open(file_path) as image:
        rgb_image = image.convert("RGB")
        rgb_image.thumbnail((64, 64))
        colors = rgb_image.getcolors(maxcolors=64 * 64)

    if not colors:
        return None

    _count, dominant = max(colors, key=lambda item: item[0])
    return closest_color_label(dominant)


def closest_color_label(rgb: tuple[int, int, int]) -> str:
    return min(COLOR_PALETTE, key=lambda color: color_distance(rgb, color[1]))[0]


def color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> int:
    return sum((left[index] - right[index]) ** 2 for index in range(3))
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && uv run pytest tests/test_recognition.py::test_detect_dominant_color_label_identifies_red tests/test_recognition.py::test_detect_dominant_color_label_identifies_yellow -q
```

预期：PASS，输出包含：

```text
2 passed
```

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/color_analysis.py backend/tests/test_recognition.py
git commit -m "feat(PicMind): add local color analysis"
```

## 任务 2：让 MockRecognizer 返回颜色标签

**文件：**
- 修改：`backend/app/services/annotation.py`
- 修改：`backend/tests/test_recognition.py`

- [ ] **步骤 1：编写失败的测试**

修改 `backend/tests/test_recognition.py` 中的 `test_mock_recognizer_tags_landscape_images`，让它使用真实临时图片路径并期待颜色标签：

```python
def test_mock_recognizer_tags_landscape_images(tmp_path):
    path = tmp_path / "landscape-yellow.png"
    PillowImage.new("RGB", (80, 60), color=(255, 230, 0)).save(path)

    result = MockRecognizer().recognize(
        ImageRecognitionInput(
            image_id="image-1",
            file_path=str(path),
            width=800,
            height=600,
            format="PNG",
        )
    )

    assert isinstance(result, RecognitionResult)
    assert result.caption == "待分析的本地图片"
    assert result.tags == ["本地图片", "landscape", "黄色"]
    assert result.objects == []
    assert result.model_used == "mock"
```

保留 `test_mock_recognizer_tags_portrait_images` 和 `test_mock_recognizer_tags_square_images` 的方向断言，但不要要求它们包含颜色；这些测试继续使用 `_image_input`，验证无真实文件时不会崩溃：

```python
def test_mock_recognizer_tags_portrait_images():
    result = MockRecognizer().recognize(_image_input(width=600, height=800))

    assert result.tags == ["本地图片", "portrait"]


def test_mock_recognizer_tags_square_images():
    result = MockRecognizer().recognize(_image_input(width=600, height=600))

    assert result.tags == ["本地图片", "square"]
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_recognition.py::test_mock_recognizer_tags_landscape_images -q
```

预期：FAIL，断言差异包含：

```text
['本地图片', 'landscape'] != ['本地图片', 'landscape', '黄色']
```

- [ ] **步骤 3：编写最少实现代码**

修改 `backend/app/services/annotation.py`，增加导入：

```python
from pathlib import Path

from app.services.color_analysis import detect_dominant_color_label
```

修改 `MockRecognizer.recognize`：

```python
class MockRecognizer:
    def recognize(self, image: ImageRecognitionInput) -> RecognitionResult:
        if image.width > image.height:
            orientation = "landscape"
        elif image.height > image.width:
            orientation = "portrait"
        else:
            orientation = "square"

        tags = ["本地图片", orientation]
        file_path = Path(image.file_path)
        if file_path.exists() and file_path.is_file():
            color_label = detect_dominant_color_label(file_path)
            if color_label is not None:
                tags.append(color_label)

        return RecognitionResult(
            caption="待分析的本地图片",
            tags=tags,
            objects=[],
            model_used="mock",
        )
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && uv run pytest tests/test_recognition.py::test_mock_recognizer_tags_landscape_images tests/test_recognition.py::test_mock_recognizer_tags_portrait_images tests/test_recognition.py::test_mock_recognizer_tags_square_images -q
```

预期：PASS，输出包含：

```text
3 passed
```

- [ ] **步骤 5：Commit**

```bash
git add backend/app/services/annotation.py backend/tests/test_recognition.py
git commit -m "feat(PicMind): tag recognized images by dominant color"
```

## 任务 3：确认颜色标签会被识别服务持久化

**文件：**
- 修改：`backend/tests/test_recognition.py`

- [ ] **步骤 1：编写失败的测试**

在 `backend/tests/test_recognition.py` 增加测试：

```python
def test_recognition_service_persists_mock_color_tag(db_session, tmp_path):
    image_path = tmp_path / "yellow-service.png"
    PillowImage.new("RGB", (32, 24), color=(255, 230, 0)).save(image_path)
    image = _stored_image(db_session, image_path)

    refreshed = RecognitionService(MockRecognizer()).recognize_image(image.id, db_session)

    assert json.loads(refreshed.annotation.tags) == ["本地图片", "landscape", "黄色"]
    assert "待分析" not in json.loads(refreshed.annotation.tags)
```

- [ ] **步骤 2：运行测试验证失败**

如果任务 2 尚未实现，运行：

```bash
cd backend && uv run pytest tests/test_recognition.py::test_recognition_service_persists_mock_color_tag -q
```

预期：FAIL，断言差异包含：

```text
['本地图片', 'landscape'] != ['本地图片', 'landscape', '黄色']
```

如果任务 2 已实现，此测试可能直接 PASS；此时通过临时注释 `MockRecognizer` 中追加 `color_label` 的两行代码来验证该测试会失败，然后恢复代码。

- [ ] **步骤 3：编写最少实现代码**

任务 2 的 `MockRecognizer` 实现已经是本测试所需的生产代码。若测试仍失败，确认 `backend/app/services/annotation.py` 中 `MockRecognizer.recognize` 完整代码为：

```python
class MockRecognizer:
    def recognize(self, image: ImageRecognitionInput) -> RecognitionResult:
        if image.width > image.height:
            orientation = "landscape"
        elif image.height > image.width:
            orientation = "portrait"
        else:
            orientation = "square"

        tags = ["本地图片", orientation]
        file_path = Path(image.file_path)
        if file_path.exists() and file_path.is_file():
            color_label = detect_dominant_color_label(file_path)
            if color_label is not None:
                tags.append(color_label)

        return RecognitionResult(
            caption="待分析的本地图片",
            tags=tags,
            objects=[],
            model_used="mock",
        )
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && uv run pytest tests/test_recognition.py::test_recognition_service_persists_mock_color_tag -q
```

预期：PASS，输出包含：

```text
1 passed
```

- [ ] **步骤 5：Commit**

```bash
git add backend/tests/test_recognition.py
git commit -m "test(PicMind): cover persisted color recognition tags"
```

## 任务 4：让 API 搜索颜色标签

**文件：**
- 修改：`backend/tests/test_api.py`

- [ ] **步骤 1：编写失败的测试**

在 `backend/tests/test_api.py` 增加测试：

```python
def test_list_images_searches_recognized_color_tag(api_client: TestClient):
    image_id = api_client.get("/api/images").json()["items"][0]["id"]
    recognize_response = api_client.post(f"/api/images/{image_id}/recognize")
    assert recognize_response.status_code == 200

    response = api_client.get("/api/images", params={"q": "红色"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == image_id
    assert "红色" in payload["items"][0]["tags"]
```

- [ ] **步骤 2：运行测试验证失败**

如果任务 2 尚未实现，运行：

```bash
cd backend && uv run pytest tests/test_api.py::test_list_images_searches_recognized_color_tag -q
```

预期：FAIL，`payload["total"]` 为 `0`，因为红色标签尚未写入 tags。

如果任务 2 已实现，此测试可能直接 PASS；此时通过临时注释 `MockRecognizer` 中追加 `color_label` 的两行代码来验证该测试会失败，然后恢复代码。

- [ ] **步骤 3：编写最少实现代码**

不需要新增 API 代码。现有 `backend/app/api/images.py` 已搜索 `Annotation.tags`：

```python
query = query.filter(
    or_(
        Image.file_path.ilike(search_pattern),
        Annotation.caption.ilike(search_pattern),
        Annotation.tags.ilike(search_pattern),
    )
)
```

生产代码来自任务 2：颜色标签必须写入 `RecognitionResult.tags`，再由 `RecognitionService` 持久化到 `Annotation.tags`。

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
cd backend && uv run pytest tests/test_api.py::test_list_images_searches_recognized_color_tag -q
```

预期：PASS，输出包含：

```text
1 passed
```

- [ ] **步骤 5：Commit**

```bash
git add backend/tests/test_api.py
git commit -m "test(PicMind): cover searching recognized color tags"
```

## 任务 5：全量验证后端与前端构建

**文件：**
- 验证：`backend/tests/test_recognition.py`
- 验证：`backend/tests/test_api.py`
- 验证：`frontend/`

- [ ] **步骤 1：运行后端全量测试**

运行：

```bash
cd backend && uv run pytest -q
```

预期：PASS，输出包含：

```text
passed
```

且没有 failed。

- [ ] **步骤 2：如果后端测试失败，修复失败测试指向的最小问题**

只允许针对失败测试做最小修复。常见需要同步的断言：

```python
assert payload["tags"] == ["本地图片", "landscape", "红色"]
```

或：

```python
assert json.loads(refreshed.annotation.tags) == ["本地图片", "landscape", "红色"]
```

- [ ] **步骤 3：运行前端构建**

运行：

```bash
npm --prefix frontend run build
```

预期：PASS，输出包含：

```text
built in
```

- [ ] **步骤 4：Commit 验证相关修正**

如果步骤 2 修改了测试或代码，运行：

```bash
git add backend/app/services/annotation.py backend/app/services/color_analysis.py backend/tests/test_recognition.py backend/tests/test_api.py
git commit -m "fix(PicMind): keep color recognition tests green"
```

如果步骤 2 没有修改任何文件，不创建空 commit。

## 自检清单

- 规格中的本地主色识别由任务 1 覆盖。
- 规格中的颜色标签写入 `tags` 由任务 2 和任务 3 覆盖。
- 规格中的搜索颜色词由任务 4 覆盖。
- 规格中的 `待分析` 只保留在未识别图片由任务 3 覆盖。
- 规格中的不直接接入 YOLO 由本计划范围控制，没有安装 YOLO 依赖、没有读取模型路径。
- `objects` 预留结构写在规格中，本阶段不改数据库结构。
- 没有新增前端代码；前端只需要构建验证。
