# Bridge CLI 进度通知与收件箱实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 实现 PicMind Local Command Bridge 的 Phase 1（外发进度通知）和 Phase 2（本地任务收件箱），支持飞书/企业微信消息推送和任务收件箱手动读取工作流。

**架构：** 在 `backend/claude_bridge/` 下创建纯 Python 模块，包含通知发送器、配置加载、收件箱管理和风险分类。运行时的 `.claude/external-inbox/` 目录由 setup 脚本创建，其内容受 `.gitignore` 保护不被提交。测试放在 `backend/tests/test_claude_bridge.py`。

**技术栈：** Python 3.11+（urllib + json 标准库）、pytest

---

## 文件结构

实现后将创建/修改以下文件：

```text
backend/
  claude_bridge/
    __init__.py              # 包标识符
    config.py                # 配置加载，从 .claude/external-inbox/config.json 读取
    notifier.py              # 飞书/企业微信 webhook 通知发送
    inbox.py                 # 收件箱管理（task CRUD、风险分类、归档）
    config.example.json      # 示例配置
    external_inbox_README.md # 运行时收件箱说明源文件
    setup_inbox.py           # 初始化 .claude/external-inbox
    send_test_notification.py # 手动发送测试通知
  tests/
    test_claude_bridge.py    # 测试（通知、收件箱、分类）

docs/
  superpowers/
    workflows/
      check-external-instructions.md # Claude Code 手动检查外部指令流程
```

---

### 任务 1：Bridge 包结构与配置加载

**文件：**
- 创建：`backend/claude_bridge/__init__.py`
- 创建：`backend/claude_bridge/config.py`
- 测试：`backend/tests/test_claude_bridge.py`

- [ ] **步骤 1：编写 BridgeConfig 的失败测试**

```python
import json
from pathlib import Path

import pytest

from claude_bridge.config import BridgeConfig


def test_config_loads_webhook_url_from_file(tmp_path: Path) -> None:
    config_dir = tmp_path / ".claude" / "external-inbox"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({
        "provider": "feishu",
        "notify_webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/test",
        "allowed_senders": ["user-1"],
        "project_name": "PicMind",
    }))

    config = BridgeConfig(path=config_file)
    config.load()

    assert config.provider == "feishu"
    assert config.notify_webhook_url == "https://open.feishu.cn/open-apis/bot/v2/hook/test"
    assert config.project_name == "PicMind"
    assert config.enabled is True


def test_config_disabled_when_no_webhook(tmp_path: Path) -> None:
    config_dir = tmp_path / ".claude" / "external-inbox"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({
        "provider": "feishu",
        "notify_webhook_url": None,
    }))

    config = BridgeConfig(path=config_file)
    config.load()

    assert config.enabled is False


def test_config_defaults_to_feishu(tmp_path: Path) -> None:
    config_dir = tmp_path / ".claude" / "external-inbox"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({}))

    config = BridgeConfig(path=config_file)
    config.load()

    assert config.provider == "feishu"
    assert config.notify_webhook_url is None
    assert config.enabled is False
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_claude_bridge.py -v
```

预期：FAIL，报错 `ModuleNotFoundError: No module named 'claude_bridge'`

- [ ] **步骤 3：编写最少实现代码**

创建空文件：

```python
# backend/claude_bridge/__init__.py
```

创建配置模块：

```python
# backend/claude_bridge/config.py

import json
from pathlib import Path


DEFAULT_CONFIG_PATH = Path(".claude/external-inbox/config.json")


class BridgeConfig:
    def __init__(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        self.path = path
        self.data: dict[str, object] = {}

    def load(self) -> None:
        with open(self.path) as f:
            self.data = json.load(f)

    @property
    def provider(self) -> str:
        return str(self.data.get("provider", "feishu"))

    @property
    def notify_webhook_url(self) -> str | None:
        value = self.data.get("notify_webhook_url")
        return str(value) if value else None

    @property
    def allowed_senders(self) -> list[str]:
        return list(self.data.get("allowed_senders", []))

    @property
    def project_name(self) -> str:
        return str(self.data.get("project_name", "PicMind"))

    @property
    def enabled(self) -> bool:
        return self.notify_webhook_url is not None

    @property
    def inbox_path(self) -> Path:
        return Path(str(self.data.get("inbox_path", ".claude/external-inbox/tasks.json")))
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_claude_bridge.py -v
```

预期：PASS，3 个测试通过

- [ ] **步骤 5：Commit**

```bash
git add backend/claude_bridge/__init__.py backend/claude_bridge/config.py backend/tests/test_claude_bridge.py
git commit -m "feat(claude-bridge): add config loading from external-inbox"
```

---

### 任务 2：通知发送器

**文件：**
- 创建：`backend/claude_bridge/notifier.py`
- 修改：`backend/tests/test_claude_bridge.py`

- [ ] **步骤 1：编写通知模块失败测试**

```python
from unittest.mock import patch

from claude_bridge.notifier import send_notification, format_feishu_payload, format_wecom_payload


def test_format_feishu_payload_contains_title_and_content() -> None:
    payload = format_feishu_payload("测试标题", "测试内容")
    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "测试标题"
    assert "测试内容" in payload["card"]["elements"][0]["content"]


def test_format_wecom_payload_contains_title_and_content() -> None:
    payload = format_wecom_payload("测试标题", "测试内容")
    assert payload["msgtype"] == "markdown"
    assert "测试标题" in payload["markdown"]["content"]
    assert "测试内容" in payload["markdown"]["content"]


def test_send_notification_returns_true_on_success() -> None:
    with patch("claude_bridge.notifier.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.status = 200
        result = send_notification(
            webhook_url="https://example.com/hook",
            title="Test",
            content="Hello",
            provider="feishu",
        )
    assert result is True


def test_send_notification_returns_false_on_failure() -> None:
    with patch("claude_bridge.notifier.urlopen", side_effect=Exception("timeout")):
        result = send_notification(
            webhook_url="https://example.com/hook",
            title="Test",
            content="Hello",
            provider="feishu",
        )
    assert result is False


def test_send_notification_raises_for_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown provider"):
        send_notification(
            webhook_url="https://example.com/hook",
            title="Test",
            content="Hello",
            provider="telegram",
        )
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_claude_bridge.py::test_format_feishu_payload_contains_title_and_content -v
```

预期：FAIL，报错 `ModuleNotFoundError: No module named 'claude_bridge.notifier'`

- [ ] **步骤 3：编写最少实现代码**

```python
# backend/claude_bridge/notifier.py

import json
import logging
from urllib.request import Request, urlopen


logger = logging.getLogger(__name__)


def format_feishu_payload(title: str, content: str) -> dict:
    return {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}},
            "elements": [{"tag": "markdown", "content": content}],
        },
    }


def format_wecom_payload(title: str, content: str) -> dict:
    return {
        "msgtype": "markdown",
        "markdown": {"content": f"## {title}\n{content}"},
    }


def send_notification(webhook_url: str, title: str, content: str, provider: str = "feishu") -> bool:
    if provider == "feishu":
        payload = format_feishu_payload(title, content)
    elif provider == "wecom":
        payload = format_wecom_payload(title, content)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(webhook_url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=10) as response:
            return response.status == 200
    except Exception:
        logger.exception("Notification failed")
        return False
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_claude_bridge.py -v
```

预期：PASS，8 个测试通过

- [ ] **步骤 5：Commit**

```bash
git add backend/claude_bridge/notifier.py backend/tests/test_claude_bridge.py
git commit -m "feat(claude-bridge): add feishu and wecom notification sender"
```

---

### 任务 3：收件箱管理

**文件：**
- 创建：`backend/claude_bridge/inbox.py`
- 修改：`backend/tests/test_claude_bridge.py`

- [ ] **步骤 1：编写收件箱模块失败测试**

```python
from claude_bridge.inbox import add_task, archive_task, classify_risk, load_tasks


def test_add_task_appends_to_task_list(tmp_path: Path) -> None:
    task = add_task("继续开发", source="manual", sender="user", inbox_dir=tmp_path)
    assert task["text"] == "继续开发"
    assert task["source"] == "manual"
    assert task["status"] == "pending"

    tasks = load_tasks(inbox_dir=tmp_path)
    assert len(tasks) == 1
    assert tasks[0]["text"] == "继续开发"


def test_classify_returns_A_for_status_queries() -> None:
    assert classify_risk("状态") == "A"
    assert classify_risk("当前进度") == "A"
    assert classify_risk("测试结果") == "A"


def test_classify_returns_B_for_planning() -> None:
    assert classify_risk("继续无人机 TOF 阶段") == "B"
    assert classify_risk("检查 YOLO 接入计划") == "B"


def test_classify_returns_C_for_modification() -> None:
    assert classify_risk("修改代码") == "C"
    assert classify_risk("添加新功能") == "C"
    assert classify_risk("修复 bug") == "C"


def test_classify_returns_D_for_high_risk_actions() -> None:
    assert classify_risk("提交代码并推送") == "D"
    assert classify_risk("删除文件") == "D"
    assert classify_risk("安装新依赖") == "D"


def test_archive_task_moves_to_processed(tmp_path: Path) -> None:
    task = add_task("测试任务", inbox_dir=tmp_path)
    archive_task(task["id"], result_summary="已完成测试", inbox_dir=tmp_path)

    pending = load_tasks(inbox_dir=tmp_path)
    assert len(pending) == 0

    processed_path = tmp_path / "processed.json"
    assert processed_path.exists()
    with open(processed_path) as f:
        processed = json.load(f)
    assert len(processed) == 1
    assert processed[0]["id"] == task["id"]
    assert processed[0]["status"] == "completed"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_claude_bridge.py::test_add_task_appends_to_task_list -v
```

预期：FAIL，报错 `ModuleNotFoundError: No module named 'claude_bridge.inbox'`

- [ ] **步骤 3：编写最少实现代码**

```python
# backend/claude_bridge/inbox.py

import json
from datetime import UTC, datetime
from pathlib import Path


DEFAULT_INBOX_DIR = Path(".claude/external-inbox")


def load_tasks(inbox_dir: Path = DEFAULT_INBOX_DIR) -> list[dict]:
    path = inbox_dir / "tasks.json"
    if not path.exists():
        return []
    with open(path) as f:
        return list(json.load(f))


def save_tasks(tasks: list[dict], inbox_dir: Path = DEFAULT_INBOX_DIR) -> None:
    inbox_dir.mkdir(parents=True, exist_ok=True)
    with open(inbox_dir / "tasks.json", "w") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def classify_risk(text: str) -> str:
    text_lower = text.lower()
    if any(word in text_lower for word in ["commit", "push", "delete", "install", "flash"]):
        return "D"
    if any(word in text for word in ["推送", "提交", "删除", "安装", "烧录"]):
        return "D"
    if any(word in text_lower for word in ["add", "change", "fix", "write", "create", "test", "build", "modify"]):
        return "C"
    if any(word in text for word in ["修改", "添加", "修复", "写代码", "运行测试"]):
        return "C"
    if any(word in text_lower for word in ["plan", "analyze", "check", "review", "continue", "next"]):
        return "B"
    if any(word in text for word in ["继续", "检查", "分析", "整理", "路线", "计划"]):
        return "B"
    return "A"


def add_task(text: str, source: str = "manual", sender: str = "user", inbox_dir: Path = DEFAULT_INBOX_DIR) -> dict:
    tasks = load_tasks(inbox_dir=inbox_dir)
    task = {
        "id": f"{datetime.now(UTC).strftime('%Y%m%d')}-{len(tasks) + 1:03d}",
        "source": source,
        "sender": sender,
        "text": text,
        "status": "pending",
        "risk": classify_risk(text),
        "created_at": datetime.now(UTC).isoformat(),
    }
    tasks.append(task)
    save_tasks(tasks, inbox_dir=inbox_dir)
    return task


def archive_task(task_id: str, result_summary: str | None = None, inbox_dir: Path = DEFAULT_INBOX_DIR) -> None:
    tasks = load_tasks(inbox_dir=inbox_dir)
    remaining = [task for task in tasks if task["id"] != task_id]
    archived = next((task for task in tasks if task["id"] == task_id), None)
    save_tasks(remaining, inbox_dir=inbox_dir)

    if not archived:
        return

    processed_path = inbox_dir / "processed.json"
    processed: list[dict] = []
    if processed_path.exists():
        with open(processed_path) as f:
            processed = list(json.load(f))
    processed.append({
        "id": task_id,
        "status": "completed",
        "result_summary": result_summary or "",
        "processed_at": datetime.now(UTC).isoformat(),
    })
    with open(processed_path, "w") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)
```

- [ ] **步骤 4：运行测试验证通过**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_claude_bridge.py -v
```

预期：PASS，14 个测试通过

- [ ] **步骤 5：Commit**

```bash
git add backend/claude_bridge/inbox.py backend/tests/test_claude_bridge.py
git commit -m "feat(claude-bridge): add inbox management and risk classification"
```

---

### 任务 4：示例配置与 setup 脚本

**文件：**
- 创建：`backend/claude_bridge/config.example.json`
- 创建：`backend/claude_bridge/external_inbox_README.md`
- 创建：`backend/claude_bridge/setup_inbox.py`

- [ ] **步骤 1：编写 setup 脚本失败测试**

```python
from claude_bridge.setup_inbox import setup_inbox


def test_setup_inbox_creates_runtime_files(tmp_path: Path) -> None:
    inbox_dir = tmp_path / ".claude" / "external-inbox"
    example_config = tmp_path / "config.example.json"
    readme_source = tmp_path / "external_inbox_README.md"
    example_config.write_text(json.dumps({"provider": "feishu"}))
    readme_source.write_text("# Inbox")

    setup_inbox(inbox_dir=inbox_dir, example_config=example_config, readme_source=readme_source)

    assert (inbox_dir / "tasks.json").read_text() == "[]"
    assert (inbox_dir / "processed.json").read_text() == "[]"
    assert (inbox_dir / "config.json").exists()
    assert (inbox_dir / "README.md").read_text() == "# Inbox"
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_claude_bridge.py::test_setup_inbox_creates_runtime_files -v
```

预期：FAIL，报错 `ModuleNotFoundError: No module named 'claude_bridge.setup_inbox'`

- [ ] **步骤 3：创建示例配置**

```json
{
  "provider": "feishu",
  "notify_webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/PASTE_YOUR_WEBHOOK_URL_HERE",
  "allowed_senders": ["your-feishu-user-id"],
  "project_name": "PicMind",
  "inbox_path": ".claude/external-inbox/tasks.json"
}
```

保存为：`backend/claude_bridge/config.example.json`

- [ ] **步骤 4：创建收件箱说明源文件**

```markdown
# Claude Bridge external inbox

This runtime directory stores local-only bridge configuration and task inbox files.

## Files

- `config.json` — local bridge configuration copied from `backend/claude_bridge/config.example.json`
- `tasks.json` — pending external instructions
- `processed.json` — completed task archive

## Safety

This directory is ignored by Git. Do not copy real webhook URLs, tokens, databases, image datasets, model files, or hardware credentials into tracked files.
```

保存为：`backend/claude_bridge/external_inbox_README.md`

- [ ] **步骤 5：编写 setup 实现代码**

```python
# backend/claude_bridge/setup_inbox.py

import json
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INBOX_DIR = PROJECT_ROOT / ".claude" / "external-inbox"
DEFAULT_EXAMPLE_CONFIG = Path(__file__).with_name("config.example.json")
DEFAULT_README_SOURCE = Path(__file__).with_name("external_inbox_README.md")


def setup_inbox(
    inbox_dir: Path = DEFAULT_INBOX_DIR,
    example_config: Path = DEFAULT_EXAMPLE_CONFIG,
    readme_source: Path = DEFAULT_README_SOURCE,
) -> None:
    inbox_dir.mkdir(parents=True, exist_ok=True)

    for name in ("tasks.json", "processed.json"):
        path = inbox_dir / name
        if not path.exists():
            with open(path, "w") as f:
                json.dump([], f)

    config_target = inbox_dir / "config.json"
    if not config_target.exists() and example_config.exists():
        shutil.copy2(example_config, config_target)

    readme_target = inbox_dir / "README.md"
    if not readme_target.exists() and readme_source.exists():
        shutil.copy2(readme_source, readme_target)

    print(f"Bridge inbox ready at {inbox_dir.resolve()}")


if __name__ == "__main__":
    setup_inbox()
```

- [ ] **步骤 6：运行测试验证通过**

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_claude_bridge.py -v
```

预期：PASS，15 个测试通过

- [ ] **步骤 7：手动验证 setup**

运行：

```bash
cd "D:/my vibe coding/picture check"
uv run python backend/claude_bridge/setup_inbox.py
```

预期输出包含：

```text
Bridge inbox ready at
```

并且 `.claude/external-inbox/` 下出现 `config.json`、`tasks.json`、`processed.json`、`README.md`。

- [ ] **步骤 8：Commit**

```bash
git add backend/claude_bridge/config.example.json backend/claude_bridge/external_inbox_README.md backend/claude_bridge/setup_inbox.py backend/tests/test_claude_bridge.py
git commit -m "feat(claude-bridge): add inbox setup files"
```

---

### 任务 5：测试通知脚本与外部指令工作流文档

**文件：**
- 创建：`backend/claude_bridge/send_test_notification.py`
- 创建：`docs/superpowers/workflows/check-external-instructions.md`

- [ ] **步骤 1：编写测试通知脚本**

```python
# backend/claude_bridge/send_test_notification.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_bridge.config import BridgeConfig
from claude_bridge.notifier import send_notification


def main() -> None:
    config = BridgeConfig()
    config.load()

    if not config.enabled or not config.notify_webhook_url:
        print("Bridge is not enabled. Configure .claude/external-inbox/config.json first.")
        sys.exit(1)

    ok = send_notification(
        webhook_url=config.notify_webhook_url,
        title="PicMind 桥接测试",
        content="桥接通知已正常发送。\n\n如果收到此消息，说明配置正确。",
        provider=config.provider,
    )
    if ok:
        print("Test notification sent successfully.")
        return

    print("Failed to send test notification. Check webhook URL and network.")
    sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **步骤 2：编写外部指令工作流文档**

```markdown
# 检查外部指令工作流

## 启动方式

在 Claude Code 中输入：

```text
检查外部指令
```

## 工作流步骤

1. Claude Code 读取 `.claude/external-inbox/tasks.json`
2. 列出所有状态为 `pending` 的任务
3. 显示每个任务的风险等级（A/B/C/D）
4. 推荐优先执行的任务
5. 等待用户选择执行哪一条
6. A/B 级可直接回复结果
7. C/D 级需要确认后才能操作
8. 执行完成后将任务移至 `processed.json`

## 风险等级说明

| 等级 | 含义 | 例子 | 行为 |
|------|------|------|------|
| A | 只读查询 | 状态、进度、结果 | 直接回答 |
| B | 规划分析 | 继续路线、检查计划 | 出方案后确认 |
| C | 项目修改 | 改代码、加功能 | 说明范围后等用户确认 |
| D | 高风险 | 提交、推送、删除、安装 | 必须二次确认 |

## 安全规则

- 不自动执行 C/D 级操作
- 拒绝包含危险词（rm -rf、push --force 等）的指令
- 所有已处理任务留痕在 `processed.json`
```

保存为：`docs/superpowers/workflows/check-external-instructions.md`

- [ ] **步骤 3：手动验证测试通知脚本未配置时安全失败**

运行：

```bash
cd "D:/my vibe coding/picture check"
uv run python backend/claude_bridge/send_test_notification.py
```

预期：如果 `.claude/external-inbox/config.json` 没有真实 webhook，输出：

```text
Bridge is not enabled. Configure .claude/external-inbox/config.json first.
```

- [ ] **步骤 4：Commit**

```bash
git add backend/claude_bridge/send_test_notification.py docs/superpowers/workflows/check-external-instructions.md
git commit -m "feat(claude-bridge): add test notification workflow"
```

---

## 完整验证

后端测试：

```bash
uv --directory "D:/my vibe coding/picture check/backend" run pytest tests/test_claude_bridge.py -v
```

预期：全部通过。

Setup 手动验证：

```bash
cd "D:/my vibe coding/picture check"
uv run python backend/claude_bridge/setup_inbox.py
```

预期：`.claude/external-inbox/` 创建成功，且仍不被 Git 跟踪。

Git 忽略验证：

```bash
git status --short
```

预期：不会显示 `.claude/external-inbox/config.json`、`tasks.json`、`processed.json`。

前端构建防回归：

```bash
npm --prefix "D:/my vibe coding/picture check/frontend" run build
```

预期：构建通过。

## 不在本计划范围内

- 飞书/企业微信 inbound callback 服务
- 自动定时读取外部任务
- 自动执行任何 C/D 级任务
- Claude API 自建代理
- 微信个人号自动化
