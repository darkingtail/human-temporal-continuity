# HTC Bootstrap 与记忆恢复

HTC 的默认使用场景不是“先安装 HTC，再开始聊天”，而是：用户已经在 Codex、Claude Code、ChatGPT 或其他工具里积累了会话、经历和未完成事项，之后才接入 HTC。

因此，Bootstrap 的目标不是偷偷搬走所有历史，而是让用户以可控、可追溯的方式建立第一条用户级记忆线。

> 线程很多，但人只有一个。HTC 的记忆范围属于用户，而不是某个会话。

## 三种恢复方式

### 1. 从现在开始

不读取旧内容。HTC 只观察之后被宿主明确提交的新回合。

适用于：用户希望先体验、只需要未来连续性，或不想整理历史。

### 2. 用户授权的历史导入

用户主动选择一个导出文件、选中的会话或自己写的摘要。HTC 只处理该来源，不读取 Codex、Claude Code、ChatGPT 等产品的私有数据库、缓存或隐藏历史。

导入流程为：

```text
ImportSource → ImportJob → Observation → Candidate → 用户决定 → Memory
```

导入成功只代表“材料已转成候选”，不代表其中的内容已经成为长期记忆。

### 3. 渐进式恢复

用户在新的对话里再次提到过去：例如“我去年年底换了工作”“假期从外地回来后一直很空落”。HTC 把这些新说法当作新的、带不确定性的证据，按来源和时间精度与已有候选或记忆合并。

它不要求用户一次性整理完人生，也不为了“看起来懂你”补造精确日期。

## 授权模型

以下几件事必须分开：

| 行为 | 含义 | 默认 |
|---|---|---|
| 选择导入来源 | 允许读取这一个用户选择的来源 | 不存在，必须显式选择 |
| 保留候选 | 用户确认它可成为本地记忆 | 需要在 Inbox 确认 |
| 跨会话内部使用 | 已确认记忆可用于未来其他会话的理解 | 关闭 |
| 主动提及 | AI 可以主动说出这段记忆 | 独立控制；负面/敏感内容默认收紧 |

其中，“候选点保留”形成 Memory；跨会话能力由用户级开关控制。关闭或撤回该开关会递增撤销版本，使之前发出的 Recall Package 失效。

导入记录提供的 `permissions` 只是提取器输出，不能越过用户级授权。

## 当前核心对象

### `ImportSource`

记录用户授权读取的来源：来源类型、定位符、内容哈希（如有）和授权范围。当前只接受 `authorization_scope: "user_selected"`。

### `ImportJob`

记录一次可重试的导入作业：所属来源、状态、处理数量、生成的候选 ID、开始/结束时间与错误信息。

同一来源内的 `source_record_id` 是稳定幂等键。重复提交同一记录不会新建候选；从同一来源创建新作业重导时，也会复用已有的 Observation/Candidate 链路。

### `BootstrapSnapshot`

记录初始基线由哪些来源、导入作业和候选建立。它只保存 ID 与时间，不是第二份记忆数据库，也不复制原始历史文本。

## CLI 最小示例

以下命令只用于本地合成数据验证。真实个人历史在存储保护和导入审查完成前不应写入当前 SQLite 原型。

```powershell
cd core

# 允许已确认的记忆跨会话用于内部理解。
uv run htc-core --db .\demo.sqlite3 policy --input .\policy.json

# 注册一个由用户选择的来源。
uv run htc-core --db .\demo.sqlite3 import-source --input .\source.json

# 创建作业、分批提交记录，并建立基线快照。
uv run htc-core --db .\demo.sqlite3 import-start --input .\job.json
uv run htc-core --db .\demo.sqlite3 import-batch --input .\batch.json
uv run htc-core --db .\demo.sqlite3 bootstrap --input .\snapshot.json
```

`batch.json` 中每条记录至少有稳定的 `source_record_id`、`observed_at` 和不可信的 `proposal`。proposal 会进入 Candidate，而非直接成为 Memory。

## 已保证的边界

- 不读取宿主私有 SQLite、缓存或隐藏会话数据库。
- 来源、作业、候选与基线快照都验证同一用户归属。
- 历史导入不绕过 Candidate Inbox。
- 旧 FR-007 SQLite 数据库会通过增量迁移获得新的用户级跨会话授权字段。
- 重复导入同一来源记录不会生成重复候选。
- 负面或敏感信息不会因为导入而自动获得主动提及授权。

## 当前未完成项

- 导入失败、暂停、取消与授权过期/撤回的完整状态机。
- `suppressed` 的审计可见投影，以及对应的 Recall Package 契约更新。
- Bootstrap/Import 的语言无关 JSON Schema。
- 真实个人数据的加密存储、物理删除与派生数据清理。
- 通用自然语言提取器、LLM 接入和正式宿主 Adapter。

Codex 的第一个项目级 Adapter MVP 已于 2026 年 8 月 19 日实现；这里的“正式宿主 Adapter”仍指完成全局安装、受控真实数据验证、存储保护和发布后的版本。当前实现见 [HTC Codex Adapter MVP](codex-adapter-mvp.md)。

这些限制是有意保留的：先把“用户知道发生了什么、能控制什么”做对，再扩大自动化程度。
