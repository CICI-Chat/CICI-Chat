# PicMind Local Command Bridge Design

## Goal

Build a safe local bridge so the user can receive PicMind/Claude Code progress notifications through a chat-style tool and send task instructions back without giving external messages direct control over the computer.

The first version should prioritize safety and reliability over full automation:

- Claude Code can send progress notifications to a configured webhook.
- External chat messages are written into a local task inbox.
- Claude Code reads the inbox only when asked or during an approved workflow.
- Risky actions still require explicit confirmation inside Claude Code.

## Context

PicMind is a local-first project with backend/frontend development, image recognition workflows, future YOLO integration, and a drone roadmap involving ESP32-S3-CAM, TOF ranging, optical-flow modules, and a separate flight controller. The user wants to continue pushing the project while not constantly watching the terminal.

The bridge should run on the same Windows computer as Claude Code. It is not a remote-control system and should not execute commands directly from WeChat, Feishu, Enterprise WeChat, or any other chat source.

## Recommended Architecture

Use a local file-based inbox with optional webhook adapters.

```text
Chat tool / phone
  -> webhook or bot callback
  -> local bridge service
  -> .claude/external-inbox/tasks.json
  -> Claude Code reads and triages
  -> Claude Code acts after confirmation when needed
  -> notification webhook sends progress back
```

The bridge has three separate responsibilities:

1. Notification sender: sends progress messages from local scripts/hooks to the chat tool.
2. Inbox writer: accepts external instructions and appends them to a local JSON task inbox.
3. Claude workflow: reads the inbox, classifies risk, and asks for confirmation before modifying code or shared state.

## Non-goals

The first version must not:

- Execute shell commands directly from chat messages.
- Let external messages trigger git commits, pushes, deletes, installs, database changes, or ESP32 flashing.
- Store chat bot tokens in Git.
- Require the PicMind app to be running.
- Replace Claude Code with a custom Claude API agent.

## Provider Strategy

Support providers through small adapters, but implement one provider first.

Recommended order:

1. Feishu webhook notification because it is straightforward for progress messages.
2. Feishu bot callback or Enterprise WeChat callback for inbound instructions.
3. Optional Bark/Windows notification for local-only alerts.

WeChat personal account automation is not recommended because it is fragile, may violate platform rules, and is harder to secure.

## Local Files

Create these files when implementing:

```text
.claude/external-inbox/
  tasks.json
  processed.json
  config.example.json
  README.md
```

Do not commit secrets:

```text
.claude/external-inbox/config.json
.claude/external-inbox/*.token
```

Recommended `tasks.json` shape:

```json
[
  {
    "id": "20260609-001",
    "source": "feishu",
    "sender": "user-redacted",
    "text": "继续无人机 TOF 模块测试路线",
    "status": "pending",
    "risk": "unknown",
    "created_at": "2026-06-09T10:30:00+08:00"
  }
]
```

Recommended `processed.json` shape:

```json
[
  {
    "id": "20260609-001",
    "status": "completed",
    "result_summary": "整理了 TOF 模块测试路线",
    "processed_at": "2026-06-09T10:45:00+08:00"
  }
]
```

Recommended `config.example.json` shape:

```json
{
  "provider": "feishu",
  "notify_webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/REDACTED",
  "allowed_senders": ["user-id-redacted"],
  "project_name": "PicMind",
  "inbox_path": ".claude/external-inbox/tasks.json"
}
```

## Risk Classification

Every inbound instruction must be classified before action.

### Level A: read-only, safe

Examples:

- 状态
- 当前进度
- 最近提交
- 测试结果
- 下一步建议

Allowed behavior:

- Summarize known state.
- Read files or git status when Claude Code is active.
- Send progress notification.

### Level B: planning or analysis

Examples:

- 继续无人机 TOF 阶段路线
- 检查 YOLO 接入计划
- 分析当前错误
- 整理下一步开发建议

Allowed behavior:

- Claude Code may answer or plan after reading the task.
- No code modification unless the user approves the next step.

### Level C: project modification

Examples:

- 修改代码
- 添加功能
- 修复 bug
- 生成文档
- 运行测试

Allowed behavior:

- Claude Code must explain likely scope before editing.
- Tests/builds can run after the user approves the task.
- Code changes follow normal project workflow and review.

### Level D: high-risk action

Examples:

- git commit
- git push
- delete files
- install dependencies
- modify database
- flash ESP32
- change system settings
- upload data/model files

Allowed behavior:

- Must require explicit confirmation inside Claude Code.
- Push/commit must follow the existing Git safety protocol.
- Destructive actions require exact confirmation text.

## Rejected or Blocked Instructions

The bridge should flag and not auto-approve messages containing destructive or unsafe phrases such as:

```text
rm -rf
reset --hard
push --force
删除所有
清空项目
提交密钥
上传 .env
跳过测试
关闭安全检查
```

These messages can still be shown to Claude Code for review, but no action should happen automatically.

## Notification Templates

### Task started

```text
PicMind 任务开始

任务：<task title>
当前阶段：<phase>
下一步：<next action>
```

### Progress update

```text
PicMind 进度更新

已完成：
- <item 1>
- <item 2>

正在进行：<current work>
```

### Needs confirmation

```text
PicMind 需要确认

请求：<requested action>
风险等级：<A/B/C/D>
原因：<why confirmation is needed>
请回到 Claude Code 确认。
```

### Blocked

```text
PicMind 遇到阻塞

问题：<blocker>
需要你提供：<missing input>
建议选项：<options>
```

### Done

```text
PicMind 任务完成

完成内容：
- <item 1>
- <item 2>

验证：<test/build/manual status>
下一步建议：<next step>
```

## Claude Code Workflow

When the user says "检查外部指令", Claude Code should:

1. Read `.claude/external-inbox/tasks.json`.
2. List pending instructions.
3. Classify each instruction by risk.
4. Recommend which instruction to handle first.
5. Ask for confirmation before Level C or Level D work.
6. Move completed tasks to `processed.json` after the user-approved work is done.

The bridge should not hide tasks from the user. If multiple tasks exist, Claude Code should display them and let the user choose unless one is clearly a read-only status request.

## Implementation Phases

### Phase 1: outbound progress notifications

Implement only local-to-chat notification.

Deliverables:

- A script or hook helper that posts text to Feishu/Enterprise WeChat webhook.
- `config.example.json` with redacted example values.
- A manual test command that sends a sample notification.

Success criteria:

- The user receives a test notification on phone/desktop chat.
- Secrets are not committed.
- Failure to notify does not block development work.

### Phase 2: local inbox

Implement local task inbox files and a command/manual workflow to read them.

Deliverables:

- `tasks.json` and `processed.json` schema.
- A sample pending task.
- A "check external instructions" workflow.

Success criteria:

- Claude Code can read pending tasks.
- Completed tasks can be archived.
- Risk classification is shown before execution.

### Phase 3: inbound chat adapter

Implement provider callback to append messages into `tasks.json`.

Deliverables:

- Local service endpoint for inbound messages.
- Sender allowlist.
- Message normalization into the task schema.

Success criteria:

- A message sent from the approved chat account appears in `tasks.json`.
- Messages from unapproved senders are ignored or logged as rejected.
- No shell command is executed by the inbound service.

### Phase 4: limited safe automation

Allow only safe read-only commands to be answered automatically.

Deliverables:

- Whitelisted commands: 状态, 进度, 当前任务, 下一步建议.
- Auto-reply through notification provider.
- Audit log of auto-replies.

Success criteria:

- Read-only status questions can be answered.
- Modification requests still wait for Claude Code confirmation.

### Phase 5: optional scheduled checks

Add a scheduler only after the inbox workflow is stable.

Deliverables:

- Periodic check for pending inbox tasks.
- Notification when new tasks are waiting.

Success criteria:

- The user is notified that tasks are waiting.
- The scheduler does not execute project changes by itself.

## Testing Strategy

Automated tests should cover:

- Task schema parsing.
- Risk classification.
- Sender allowlist behavior.
- Blocked phrase detection.
- Notification payload formatting.
- Inbound adapter appends tasks without executing commands.

Manual verification should cover:

1. Send a sample progress notification.
2. Add a sample task to `tasks.json`.
3. Ask Claude Code to check external instructions.
4. Confirm Level A/B tasks are summarized safely.
5. Confirm Level C/D tasks require explicit confirmation.
6. Send a blocked phrase and confirm it is not executed.

## Security Requirements

- Store real webhook URLs and tokens only in ignored local config files.
- Never commit `.env`, API keys, bot tokens, local databases, image datasets, model weights, or ESP32 flashing credentials.
- Treat inbound messages as untrusted user input.
- Never execute shell commands from the bridge service.
- Require confirmation for commits, pushes, file deletion, dependency installation, database operations, ESP32 flashing, and system configuration changes.
- Keep an audit trail of received tasks and processed tasks.

## Recommended First Build

Start with Phase 1 and Phase 2 only:

1. Add outbound notification helper.
2. Add local inbox schema and examples.
3. Add documentation for "检查外部指令".

Do not implement inbound chat callbacks until notification and local inbox are stable.
