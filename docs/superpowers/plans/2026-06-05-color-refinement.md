# 颜色细分识别实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将本地颜色识别从粗粒度颜色升级为覆盖主要色系深浅等级的单一颜色标签。

**架构：** 保留现有 `detect_dominant_color_label()` 对外接口，扩展 `backend/app/services/color_analysis.py` 内的颜色调色板。识别流程仍是读取图片主色、计算 RGB 距离、返回最接近的一个标签；搜索继续复用已有 tags 搜索能力。

**技术栈：** Python、Pillow、pytest、FastAPI/SQLAlchemy 现有识别服务。

---

## 文件结构

- 修改：`backend/app/services/color_analysis.py`
  - 职责：维护颜色调色板，读取图片主色，返回最接近的单一颜色标签。
- 修改：`backend/tests/test_recognition.py`
  - 职责：覆盖颜色分析、MockRecognizer 标签输出、RecognitionService 持久化行为。
- 修改：`backend/tests/test_api.py`
  - 职责：验证细分颜色标签仍可通过现有图库搜索接口检索。

---

### 任务 1：为绿色深浅写失败测试

**文件：**
- 修改：`backend/tests/test_recognition.py:192-203`
- 修改：`backend/app/services/color_analysis.py:6-18`

- [ ] **步骤 1：编写失败的测试**

在 `backend/tests/test_recognition.py` 的颜色测试区域追加：

```python
def test_detect_dominant_color_label_identifies_light_green(tmp_path):
    path = tmp_path / "light-green.png"
    PillowImage.new("RGB", (20, 20), color=(187, 247, 208)).save(path)

    assert detect_dominant_color_label(path) == "浅绿色"


def test_detect_dominant_color_label_identifies_green(tmp_path):
    path = tmp_path / "green.png"
    PillowImage.new("RGB", (20, 20), color=(34, 139, 34)).save(path)

    assert detect_dominant_color_label(path) == "绿色"


def test_detect_dominant_color_label_identifies_dark_green(tmp_path):
    path = tmp_path / "dark-green.png"
    PillowImage.new("RGB", (20, 20), color=(20, 83, 45)).save(path)

    assert detect_dominant_color_label(path) == "深绿色"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_recognition.py::test_detect_dominant_color_label_identifies_light_green tests/test_recognition.py::test_detect_dominant_color_label_identifies_green tests/test_recognition.py::test_detect_dominant_color_label_identifies_dark_green -q
```

预期：至少 `light_green` 和 `dark_green` 失败，因为当前调色板没有 `浅绿色`、`深绿色`。

- [ ] **步骤 3：编写最少实现代码**

将 `backend/app/services/color_analysis.py` 中的 `COLOR_PALETTE` 绿色项扩展为：

```python
COLOR_PALETTE: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("黑色", (0, 0, 0)),
    ("白色", (255, 255, 255)),
    ("灰色", (128, 128, 128)),
    ("红色", (220, 20, 60)),
    ("橙色", (255, 140, 0)),
    ("黄色", (255, 215, 0)),
    ("深绿色", (20, 83, 45)),
    ("绿色", (34, 139, 34)),
    ("浅绿色", (187, 247, 208)),
    ("蓝色", (30, 144, 255)),
    ("紫色", (128, 0, 128)),
    ("粉色", (255, 105, 180)),
    ("棕色", (139, 69, 19)),
)
```

- [ ] **步骤 4：运行测试验证通过**

运行同一步骤 2 命令。

预期：3 个测试通过。

- [ ] **步骤 5：Commit**

本次用户要求不提交代码。记录应提交文件但不要执行 commit：

```bash
git add backend/app/services/color_analysis.py backend/tests/test_recognition.py
# 不执行 git commit
```

---

### 任务 2：覆盖所有主要色系深浅调色板

**文件：**
- 修改：`backend/tests/test_recognition.py:192-230`
- 修改：`backend/app/services/color_analysis.py:6-24`

- [ ] **步骤 1：编写失败的测试**

在 `backend/tests/test_recognition.py` 的颜色测试区域追加参数化测试：

```python
@pytest.mark.parametrize(
    ("rgb", "expected_label"),
    [
        ((254, 202, 202), "浅红色"),
        ((220, 20, 60), "红色"),
        ((127, 29, 29), "深红色"),
        ((254, 215, 170), "浅橙色"),
        ((255, 140, 0), "橙色"),
        ((124, 45, 18), "深橙色"),
        ((254, 249, 195), "浅黄色"),
        ((255, 215, 0), "黄色"),
        ((113, 63, 18), "深黄色"),
        ((207, 250, 254), "浅青色"),
        ((6, 182, 212), "青色"),
        ((21, 94, 117), "深青色"),
        ((191, 219, 254), "浅蓝色"),
        ((30, 144, 255), "蓝色"),
        ((30, 58, 138), "深蓝色"),
        ((233, 213, 255), "浅紫色"),
        ((128, 0, 128), "紫色"),
        ((88, 28, 135), "深紫色"),
        ((252, 231, 243), "浅粉色"),
        ((255, 105, 180), "粉色"),
        ((131, 24, 67), "深粉色"),
        ((231, 209, 185), "浅棕色"),
        ((139, 69, 19), "棕色"),
        ((67, 36, 17), "深棕色"),
        ((229, 231, 235), "浅灰色"),
        ((128, 128, 128), "灰色"),
        ((31, 41, 55), "深灰色"),
        ((0, 0, 0), "黑色"),
        ((255, 255, 255), "白色"),
    ],
)
def test_detect_dominant_color_label_identifies_refined_palette(tmp_path, rgb, expected_label):
    path = tmp_path / f"{expected_label}.png"
    PillowImage.new("RGB", (20, 20), color=rgb).save(path)

    assert detect_dominant_color_label(path) == expected_label
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_recognition.py::test_detect_dominant_color_label_identifies_refined_palette -q
```

预期：多个参数失败，因为当前调色板尚未包含所有深浅标签。

- [ ] **步骤 3：编写最少实现代码**

将 `backend/app/services/color_analysis.py` 的 `COLOR_PALETTE` 完整替换为：

```python
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
```

- [ ] **步骤 4：运行测试验证通过**

运行同一步骤 2 命令。

预期：参数化测试全部通过。

- [ ] **步骤 5：Commit**

本次用户要求不提交代码。记录应提交文件但不要执行 commit：

```bash
git add backend/app/services/color_analysis.py backend/tests/test_recognition.py
# 不执行 git commit
```

---

### 任务 3：更新 MockRecognizer 与持久化行为测试

**文件：**
- 修改：`backend/tests/test_recognition.py:50-67`
- 修改：`backend/tests/test_recognition.py:131-139`
- 修改：`backend/app/services/color_analysis.py:6-42`

- [ ] **步骤 1：编写失败的测试**

更新 `test_mock_recognizer_tags_landscape_images`，让黄色样例变为浅黄色样例：

```python
def test_mock_recognizer_tags_landscape_images(tmp_path):
    path = tmp_path / "landscape-light-yellow.png"
    PillowImage.new("RGB", (80, 60), color=(254, 249, 195)).save(path)

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
    assert result.tags == ["本地图片", "landscape", "浅黄色"]
    assert result.objects == []
    assert result.model_used == "mock"
```

更新 `test_recognition_service_persists_mock_color_tag`：

```python
def test_recognition_service_persists_mock_color_tag(db_session, tmp_path):
    image_path = tmp_path / "dark-blue-service.png"
    PillowImage.new("RGB", (32, 24), color=(30, 58, 138)).save(image_path)
    image = _stored_image(db_session, image_path)

    refreshed = RecognitionService(MockRecognizer()).recognize_image(image.id, db_session)

    assert json.loads(refreshed.annotation.tags) == ["本地图片", "landscape", "深蓝色"]
    assert "待分析" not in json.loads(refreshed.annotation.tags)
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
cd backend && uv run pytest tests/test_recognition.py::test_mock_recognizer_tags_landscape_images tests/test_recognition.py::test_recognition_service_persists_mock_color_tag -q
```

预期：如果任务 2 尚未实现，会失败；如果任务 2 已实现，应通过。若已通过，说明前一任务已经覆盖了 MockRecognizer 的颜色调用路径。

- [ ] **步骤 3：编写最少实现代码**

如果测试失败，确认 `MockRecognizer.recognize()` 中仍然使用：

```python
color_label = detect_dominant_color_label(file_path)
if color_label is not None:
    tags.append(color_label)
```

不要添加粗色标签，不要添加 `肉色` 或 `肤色`。

- [ ] **步骤 4：运行测试验证通过**

运行同一步骤 2 命令。

预期：2 个测试通过。

- [ ] **步骤 5：Commit**

本次用户要求不提交代码。记录应提交文件但不要执行 commit：

```bash
git add backend/tests/test_recognition.py backend/app/services/color_analysis.py
# 不执行 git commit
```

---

### 任务 4：更新 API 搜索颜色标签测试

**文件：**
- 修改：`backend/tests/test_api.py:327-352`
- 修改：`backend/app/services/color_analysis.py:6-42`

- [ ] **步骤 1：编写失败的测试**

在 `backend/tests/test_api.py` 中更新红色识别期望，让样例红图按细分色表返回明确标签。当前 API fixture 的 sample image 是纯红，预期仍保持 `红色`，只需验证现有标签搜索路径能检索细分后的颜色标签：

```python
def test_list_images_searches_recognized_refined_color_tag(api_client: TestClient):
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

如果已有 `test_list_images_searches_recognized_color_tag` 内容相同，只重命名为 `test_list_images_searches_recognized_refined_color_tag` 并保持断言。

- [ ] **步骤 2：运行测试验证失败或确认已有行为**

运行：

```bash
cd backend && uv run pytest tests/test_api.py::test_list_images_searches_recognized_refined_color_tag -q
```

预期：如果只重命名且红色仍为 `红色`，测试可能直接通过；若直接通过，记录原因：API 搜索行为不需要生产代码变更，因为颜色标签仍通过 tags 保存。

- [ ] **步骤 3：编写最少实现代码**

不修改 API 搜索代码。现有 `Annotation.tags.ilike(search_pattern)` 已经能搜索新颜色标签。

- [ ] **步骤 4：运行测试验证通过**

运行同一步骤 2 命令。

预期：测试通过。

- [ ] **步骤 5：Commit**

本次用户要求不提交代码。记录应提交文件但不要执行 commit：

```bash
git add backend/tests/test_api.py
# 不执行 git commit
```

---

### 任务 5：最终验证

**文件：**
- 修改：`backend/app/services/color_analysis.py`
- 修改：`backend/tests/test_recognition.py`
- 修改：`backend/tests/test_api.py`

- [ ] **步骤 1：运行颜色识别测试**

运行：

```bash
cd backend && uv run pytest tests/test_recognition.py -q
```

预期：所有 recognition 测试通过。

- [ ] **步骤 2：运行 API 测试**

运行：

```bash
cd backend && uv run pytest tests/test_api.py -q
```

预期：所有 API 测试通过。

- [ ] **步骤 3：运行完整后端测试**

运行：

```bash
cd backend && uv run pytest -q
```

预期：全部测试通过。

- [ ] **步骤 4：检查工作区差异**

运行：

```bash
git diff -- backend/app/services/color_analysis.py backend/tests/test_recognition.py backend/tests/test_api.py
```

预期：差异只包含颜色调色板和相关测试更新。

- [ ] **步骤 5：不提交代码**

用户要求本计划不提交代码。实现完成后停在未提交状态，向用户报告验证结果并等待下一步指令。
