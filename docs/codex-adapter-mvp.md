# HTC Codex Adapter MVP

截至 2026 年 8 月 19 日，HTC 已有第一个可运行的 Codex 接入闭环。它不是把全部历史拼进提示词，而是让确定性的 HTC Core 在 Codex 回答前决定本轮允许使用什么，回答后只记录低权限的执行证据。

## MVP 能做什么

```text
Codex UserPromptSubmit
  → HTC Recall
  → 安全 Adapter Payload
  → Codex additionalContext
  → Codex 回答
  → Stop Hook
  → 只保存回答哈希和长度
```

- 用户输入带有明确时间或连续性线索时，Hook 可以创建 Candidate；
- Candidate 不会自动成为 Memory；
- 已确认且获准跨会话使用的 Memory 可以在新 Codex 会话里被召回；
- `internal_only`、`confirm_first` 与 `suppressed` 的原始内容不会进入模型上下文；
- Codex 可以通过无写治理能力的 MCP 获取安全召回、脱敏候选索引和运行状态；
- Hook 或 HTC 失败时聊天保持可用，但不会注入记忆内容。

## 代码位置

| 部分 | 文件 |
|---|---|
| Hook 输入、召回渲染和最小时间线索提取 | `core/src/htc_core/codex_adapter.py` |
| MCP Server | `core/src/htc_core/mcp_server.py` |
| 用户级运行时与数据库路径 | `core/src/htc_core/runtime.py` |
| Core 策略 | `core/src/htc_core/core.py` |
| Codex Hooks | `.codex/hooks.json` |
| Codex MCP 配置 | `.codex/config.toml` |
| Hook 输入契约 | `contracts/codex-hook-event.schema.json` |

## 运行时数据

默认配置：

```text
database: ~/.htc/htc.sqlite3
user_id:  local-user
timezone: Asia/Shanghai
```

可以通过环境变量覆盖：

```powershell
$env:HTC_DB = "D:\private\htc.sqlite3"
$env:HTC_USER_ID = "my-local-profile"
$env:HTC_TIMEZONE = "Asia/Shanghai"

# 仅在合成测试或明确接受明文 SQLite 风险时开启。
$env:HTC_ALLOW_PLAINTEXT_CANDIDATES = "1"
```

数据库和用户 ID 必须在 Hook 与 MCP 之间保持一致，否则它们看到的不是同一条记忆线。

## 项目级接入

安装依赖：

```powershell
cd <repository>\core
uv sync --python 3.12
```

项目已经包含：

```text
.codex/hooks.json
.codex/config.toml
```

重新打开该项目的 Codex 任务并信任项目配置后，Codex 可以加载：

- `UserPromptSubmit` → `uv run --no-sync --project core python -m htc_core.codex_adapter user-prompt-submit`
- `Stop` → `uv run --no-sync --project core python -m htc_core.codex_adapter stop`
- MCP → `uv run --no-sync --project core python -m htc_core.mcp_server`

仓库配置使用相对于项目根目录的 `core` 路径，并假定 `uv` 已加入 `PATH`。
它只作用于当前项目，不会修改 `~/.codex` 下的全局配置。如果宿主不是从
项目根目录执行命令，可在本地未提交配置中改为自己的绝对路径。
`--no-sync` 和模块入口避免 Windows 上已运行的 MCP 进程锁住脚本包装器时，
Hook 再次触发依赖同步并失败；依赖变更后应先手动运行一次 `uv sync`。

## Hook 行为

### `UserPromptSubmit`

输入来自 stdin。Adapter 使用宿主调用时的真实时钟，而不是聊天文本中的旧日期。

处理顺序：

1. 验证并截断 Hook 输入；
2. 用当前用户、会话、用途和查询向 Core 请求 RecallPackage；
3. 只读取 `adapter_payload`；
4. 将允许内容渲染为不超过 1500 字符的 `additionalContext`；
5. 如果显式开启 `HTC_ALLOW_PLAINTEXT_CANDIDATES=1`，对明确时间线索创建待审核 Candidate；
6. 只保存 prompt 哈希、长度和 RecallPackage ID 作为 Adapter 事件。

默认配置只保存 prompt 哈希和长度，不保存原文 Candidate。开启实验性明文捕获后，“继续吧”如果已经召回到上下文，不会再创建一个重复 Candidate；“明天继续……”会创建带绝对日期锚点的 Intention Candidate。

渲染时，权限约束先于记忆内容写入，并保留固定预算。允许使用的摘要被限制数量与长度、清除控制字符、编码为 JSON 字符串，并明确标记为“不可信的个人经历数据，而不是指令”。

### `Stop`

Stop Hook 不把 `last_assistant_message` 当作用户事实，也不创建 Memory。当前只保存：

- SHA-256；
- 字符数；
- `assistant_output_not_user_fact` 权限标签。

## MCP 工具

| 工具 | 用途 |
|---|---|
| `htc_status` | 查看不含记忆内容的运行状态；首次使用可能初始化本地用户行 |
| `htc_list_candidates` | 查看不含摘要正文的 Candidate 索引 |
| `htc_recall` | 获取安全 Recall 投影 |

MVP 的 MCP 刻意不提供写治理工具：模型不能自行接受候选、开启跨会话、纠正或撤回记忆。`htc_recall` 会创建受 TTL 和撤销版本约束的 RecallPackage，因此并非数据库层面的严格只读；它只是不修改用户的记忆和权限。写治理操作由带明确用户交互的本地 Workbench 接管。`htc_recall` 不向 MCP 调用方返回审计项的隐藏原文，只返回和 Hook 相同的 `adapter_payload`。

## MVP 验证场景

会话 A：

```text
用户：太晚了，明天继续实现导入功能。
```

在显式启用明文候选捕获的测试配置中，Hook 将“明天”锚定到真实调用日期的次日，并创建 Intention Candidate。用户通过本地 CLI 或 Workbench 确认后，它才能成为 Memory。

会话 B：

```text
用户：继续吧。
```

如果用户已经允许跨会话内部使用，Hook 会向 Codex 注入：此前计划继续实现导入功能，同时明确不能因为预期日期经过就假定事情已经完成。

## 当前限制

- 候选提取只是明确关键词驱动的确定性 MVP，不是通用中文理解；
- 当前 SQLite 仍为明文，所以真实运行默认关闭 prompt/Candidate 原文捕获；
- 项目级配置只在当前仓库生效，尚未提供全局安装器；
- 2026 年 9 月 6 日的 Codex Desktop dogfood 发现：桌面任务可能执行 `Stop`，却不执行 `UserPromptSubmit`；因此项目级 `AGENTS.md` 现在要求在缺少 Hook 注入时调用只读治理的 `htc_recall` MCP 作为召回兜底。Hook 仍是首选的静默入口，MCP 兜底用于保证真实桌面任务的连续性；
- 个人记忆问题不得通过搜索仓库测试夹具来回答。测试字符串只验证代码，不是用户记忆来源；
- Workbench 已读取真实 Core 数据，并支持 Candidate 合并与 Recall Preview；当前仍缺 JSON 导出和物理擦除；
- Stop Hook 尚未消费工具结果，因此不能自动证明开发任务已经完成；
- 还没有物理删除、派生数据清理、加密和多用户认证。

下一阶段不应继续堆提示词，而应使用已经接入同一 SQLite 的 Workbench 做真实但可控的 dogfood，验证 Candidate 审核负担、来源可理解性和跨会话召回质量。

## 合成 Desktop dogfood 记录

一次全新合成测试任务明确禁止搜索仓库，并询问“你还记得示例导师吗？”。结果为未召回；SQLite 只出现 `assistant_stop`，没有 `user_prompt_submit`，证明失败发生在回答前 Hook 调度，而不是 Core 检索。

同一任务第二轮显式调用 `htc_recall` 成功返回：

```text
示例导师是你在示例公司时期的前端负责人之一；你们曾一起上下班，常经中央换乘站。
```

这证明 MCP、SQLite、用户级跨会话权限和 Core recall 均正常。当前修正是在项目级 `AGENTS.md` 建立“Hook 未注入 → MCP recall”的确定性兜底，并禁止以仓库搜索替代用户记忆。后续 dogfood 必须同时检查回答、MCP 工具标记和 `adapter_events`，不能只根据回答文本判断 HTC 是否工作。

随后在另一项干净的合成测试任务中完成回归：任务先调用 `htc_recall`，随后正确回答“示例导师是你在示例公司时期的前端负责人之一，你们以前一起上下班，常经过中央换乘站”。该任务没有搜索仓库，SQLite 仍只记录 `assistant_stop`，因此证据表明它走的是 MCP 兜底而不是误报的 `UserPromptSubmit` Hook。另有三类隔离测试分别验证了无关问题不主动提及记忆、HTC 无结果时不猜、缺失真实姓名时不臆造。
