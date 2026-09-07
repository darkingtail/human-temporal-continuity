# HTC Memory Workbench MVP

> 状态：产品规格与首个真实闭环 0.2
>
> 日期：2026-07-26
>
> 关联：FR-003、FR-010

> 2026-09-06 实现状态：Timeline、Candidate Inbox、Memory Detail、来源安全投影、
> 治理解释、纠正、逻辑撤回、关闭主动提及、用户级跨会话开关和 Recall Preview
> 已经连接真实 HTC Core，Candidate 也可以合并到已有 Memory 并保留来源链。
> Conversations 来源审计也已连接真实 Core；JSON 导出仍属于后续切片。

## 1. 核心命题

线程很多，但人只有一个。HTC 的产品边界是用户级记忆，不是会话级记忆。

Memory Workbench 是一个本地优先的个人记忆工作台。它帮助长期使用 AI 的个人用户，把分散在不同会话里的经历、关系、事实、意图和变化沉淀成一条可查看、可纠正、可控制的用户级记忆线。

它关注的不是狭义的“AI 如何记住用户画像”，而是 AI 如何理解一个人在时间中的连续生活上下文：发生过什么，和谁有关，哪些事实仍然有效，哪些意图还没闭环，哪些感受或意义会影响现在，以及哪些内容即使相关也不应主动说出口。

一句话：HTC Memory Workbench 不是聊天产品，而是一个跨会话的个人记忆中枢，把用户分散在多个 AI 对话中的经历、关系、事实、意图和变化，整理成由用户控制的连续记忆线。

它不是新的陪伴聊天产品，不是聊天记录浏览器，也不是某个 Agent 的专用 Skill。聊天应用、Codex、Hermes、Claude、手动笔记或导出的聊天记录都只是来源。真正的产品对象是同一个用户的连续记忆。

## 2. 产品形态

Memory Workbench 是 Human Memory Core 之上的可视化治理台。

```text
Conversation A: 工作
Conversation B: 倾诉
Conversation C: 医院检查
Conversation D: 项目设计
Manual note / exported chat / future adapter
        ↓ observe
HTC Human Memory Core
        ↓ normalize, merge, suppress, recall
Memory Workbench
        ↓ user confirms, corrects, hides, deletes
User-level Memory Layer
```

第一版产品形式：

- 本地 Web App；
- 本地 SQLite 或等价本地存储；
- 一个用户；
- 多个 Conversation Source；
- 统一 Timeline；
- 跨会话 Candidate Inbox；
- Memory Detail 治理页；
- Recall Preview 调试页；
- 手动导入和 adapter 提交流程。

第一版不追求漂亮陪伴聊天 UI。它要先证明一件事：用户可以看见 AI 记住了什么，并决定这些记忆以后如何被使用。

## 3. 非目标

- 不直接读取 Codex、ChatGPT、Claude 或其他产品的私有 SQLite / IndexedDB / 内部缓存；
- 不偷偷全量导入用户所有历史会话；
- 不把聊天记录永久归档为产品核心；
- 不做多人协作、团队知识库或企业 CRM；
- 不做云同步、移动端、浏览器插件和通知系统；
- 不做心理诊断、人格画像或自动人生总结；
- 不把所有记忆自动写入长期存储；
- 不把 Workbench 做成另一个聊天应用。

内部存储属于 HTC 自己。外部产品通过 Connector / Adapter / Export Importer 提交 observation，而不是让 HTC 依赖它们的私有数据库结构。

## 4. 用户体验原则

### 4.1 用户级优先

主页面回答：

> 作为同一个人，我最近发生了什么？哪些事情仍然影响我？AI 现在记得什么？

而不是：

> 这个聊天窗口里说过什么？

### 4.2 会话是来源

Conversation 只证明一条记忆从哪里来、何时被说过、由谁纠正过。Memory 归属于 User。

```text
Wrong: conversation owns memory
Right: user owns memory; conversation is source evidence
```

### 4.3 候选先进入 Inbox

第一版默认保守。新的候选记忆先进入 Inbox，用户确认、修改或拒绝后再进入稳定记忆层。

低风险事实可以被标为 `suggested`，但仍应可见、可撤回。敏感内容必须最小化并默认禁止主动表达。

### 4.4 召回必须受当前会话限制

跨会话共享记忆不等于每个会话都能拿到全部记忆。每次回答前，当前会话只能获得用途绑定、短期有效、经过表达门控的 RecallPackage。

### 4.5 控制感优先于炫耀记忆

Workbench 可以解释内部状态；聊天中默认不播报内部字段。用户需要在 Workbench 里有控制感，在聊天里感到自然。

## 5. 信息架构

第一版保留六个入口：

| 页面 | 目的 | 第一版必须有 |
| --- | --- | --- |
| Timeline | 看用户级记忆线 | 是 |
| Inbox | 审核跨会话候选记忆 | 是 |
| Memory Detail | 查看来源、状态、权限并纠正 | 是 |
| Conversations | 审计来源会话 | 是 |
| Recall Preview | 模拟某会话会想起什么 | 是 |
| Settings | 全局保存与表达偏好 | 是 |

不做独立聊天页。未来可以有 Demo Chat，但它不是 MVP 主页面。

## 6. 核心页面

### 6.1 Timeline

Timeline 是用户级生活线，按时间展示已确认或高置信的 Memory。

每条 Timeline item 显示：

- 时间范围与精度；
- 类型；
- 克制摘要；
- 当前状态；
- 敏感标记；
- 是否有未闭环后续；
- 来源数量；
- 最近一次确认或纠正时间。

示例：

```text
2030-07-23 下午（合成示例）
健康检查：因身体不适就诊，当前检查未见明显异常；进一步检查为可选建议，未安排。
状态：已发生 / 当前结论已知 / 后续可选
权限：内部可用，默认不主动提
来源：2 条会话 + 1 个附件
```

Timeline 不展示原始长聊天，只展示用户可读的规范化记忆。

### 6.2 Inbox

Inbox 是候选记忆审核入口。所有新旧会话产生的 Candidate 都进入这里。

每张候选卡显示：

- 候选摘要；
- 触发来源；
- 建议类型；
- 时间解析；
- 置信度；
- 敏感级别；
- 潜在冲突；
- 建议动作。

用户操作：

- 确认；
- 修改后确认；
- 合并到已有记忆；
- 只在当前会话使用；
- 不要主动提；
- 降级为普通上下文；
- 删除候选；
- 标记“不是现实，是测试/假设/引用”。

Inbox 是防止“AI 偷偷记住一切”的关键界面。

### 6.3 Memory Detail

Memory Detail 是单条记忆的治理页。

必须展示：

- 规范化内容；
- 类型：Episode / State / Intention / Meaning / Pattern；
- 时间：event_time、anchor_time、expected_at、valid_from / valid_to、observed_at；
- 状态：current / candidate / superseded / retracted / disputed；
- 结果：known / unknown；
- 来源列表；
- 纠正历史；
- 合并关系；
- 敏感等级；
- 权限：持久保存、跨会话内部使用、主动表达；
- 最近召回记录；
- 删除和撤回操作。

用户可以直接编辑：

- 标题与摘要；
- 时间精度；
- 人名和组织名；
- 状态；
- 是否已完成、取消或仍未知；
- 是否允许主动提起；
- 是否删除。

### 6.4 Conversations（已实现）

Conversations 不是聊天记录浏览器，而是 Workbench 内的来源审计抽屉。
它只读取 HTC 自己保存的最小证据，不读取宿主产品的私有数据库，也不返回
Adapter Event payload。

每个 Conversation 显示：

- conversation_id；
- 来源类型：Observation、Adapter Event 或 mixed；
- 首次活动时间；
- 最近活动时间；
- Observation 数量；
- Candidate 总数与待处理数量；
- 关联 Memory 数量；
- Adapter Event 数量。

用户可以在同一抽屉内打开一个 Conversation，查看最小化 Observation excerpt、
Candidate 状态、关联 Memory 和 Adapter Event 类型，再返回列表。当前有效的
Memory 可以直接跳转到现有 Memory Detail。所有列表和详情都按当前 user_id 隔离，
其他用户或未知会话返回 404。

### 6.5 Recall Preview

Recall Preview 用于验证“这个会话现在会想起什么”。

输入：

- conversation_id；
- 当前消息；
- 当前时间；
- purpose；
- authorization_level；
- recall budget。

输出：

- allowed_to_use；
- internal_only；
- confirm_first；
- suppressed；
- expired_or_needs_refresh；
- 为什么选中或抑制。

示例：

```yaml
conversation: work-chat
current_message: "这个需求流程好乱。"
allowed_to_use:
  - 当前公司流程混乱反复让用户烦躁
internal_only:
  - 用户对不稳定环境更容易焦虑
suppressed:
  - 健康检查细节，与当前问题无关
  - 用户要求不要主动提的敏感背景
```

这个页面用于调试和建立信任，不代表聊天里会逐项展示。

当前实现会为每次打开的预览抽屉创建一个模拟 conversation id，并使用服务端
真实时钟签发 RecallPackage。Workbench 向记忆所有者展示匹配记忆的摘要和分类，
同时单独展示 Adapter 实际得到的较窄投影，因此可以验证 `internal_only` 和
`confirm_first` 没有泄露正文。RecallPackage 的 TTL 表示授权结果失效，不表示
SQLite 中的最小审计记录会在到期时自动物理清除。

### 6.6 Settings

第一版只需要最小设置：

- 默认是否允许普通记忆持久保存；
- 敏感记忆是否必须逐条确认；
- 默认是否允许主动表达个人经历；
- 是否启用自动候选提取；
- 本地数据库位置；
- 数据导出；
- 全部暂停观察；
- 删除所有召回包和候选缓存。

## 7. 最小对象模型

### 7.1 User

```ts
type User = {
  id: string;
  displayName?: string;
  timezone: string;
  memoryDefaults: MemoryDefaults;
  createdAt: string;
  updatedAt: string;
};
```

第一版只有一个 User，但模型不能把 user_id 省掉。

### 7.2 Conversation

```ts
type Conversation = {
  id: string;
  userId: string;
  sourceApp: "codex" | "manual" | "hermes" | "chatgpt_export" | "claude_export" | "other";
  externalId?: string;
  title?: string;
  startedAt?: string;
  lastObservedAt?: string;
  trustLevel: "trusted_host" | "user_import" | "manual" | "unknown";
};
```

Conversation 是 Source container，不拥有 Memory。

### 7.3 Source

```ts
type Source = {
  id: string;
  userId: string;
  conversationId?: string;
  sourceApp: string;
  turnId?: string;
  attachmentId?: string;
  observedAt: string;
  eventTime?: TimeRange;
  speechAct: "actual" | "hypothetical" | "quoted" | "roleplay" | "test" | "uncertain";
  rawExcerptHash?: string;
  redactedExcerpt?: string;
};
```

Source 可以保存短摘录或 hash，但不要求保存完整原文。

### 7.4 Candidate

```ts
type Candidate = {
  id: string;
  userId: string;
  sourceIds: string[];
  suggestedType: "Episode" | "State" | "Intention" | "Meaning" | "Pattern";
  summary: string;
  time: TimeRange;
  confidence: number;
  sensitivity: Sensitivity;
  conflictsWith?: string[];
  proposedAction: "create" | "merge" | "correct" | "suppress" | "ignore";
  status: "pending" | "accepted" | "edited" | "rejected" | "expired";
};
```

### 7.5 Memory

```ts
type Memory = {
  id: string;
  userId: string;
  type: "Episode" | "State" | "Intention" | "Meaning" | "Pattern";
  title: string;
  summary: string;
  time: MemoryTime;
  epistemicStatus: "candidate" | "current" | "superseded" | "retracted" | "disputed";
  outcome?: "known" | "unknown";
  sourceIds: string[];
  supersedes?: string[];
  correctedBy?: string[];
  sensitivity: Sensitivity;
  permissions: MemoryPermissions;
  importance: "low" | "medium" | "high";
  lastConfirmedAt?: string;
  createdAt: string;
  updatedAt: string;
};
```

### 7.6 RecallPackage

```ts
type RecallPackage = {
  id: string;
  userId: string;
  conversationId: string;
  purpose: string;
  issuedAt: string;
  expiresAt: string;
  packageVersion: string;
  allowedToUse: RecallItem[];
  internalOnly: RecallItem[];
  confirmFirst: RecallItem[];
  suppressed: RecallItem[];
  reasons: Record<string, string>;
};
```

RecallPackage 是短期、用途绑定的结果，不能被 adapter 跨话题重复使用。

### 7.7 Shared Types

```ts
type TimeRange = {
  start?: string;
  end?: string;
  precision: "instant" | "day" | "month" | "year" | "range" | "unknown";
  timezone?: string;
  originalText?: string;
  confidence: number;
};

type Sensitivity = "normal" | "personal" | "sensitive" | "forbidden";

type MemoryTime = {
  eventTime?: TimeRange;
  anchorTime?: string;
  expectedAt?: TimeRange;
  validFrom?: string;
  validTo?: string;
  observedAt: string;
};

type MemoryPermissions = {
  persist: boolean;
  crossSessionInternalUse: boolean;
  proactiveExpression: boolean;
  minimizedOnly: boolean;
};

type MemoryDefaults = {
  persistNormal: boolean;
  sensitiveRequiresConfirmation: boolean;
  proactiveExpressionDefault: boolean;
};

type RecallItem = {
  memoryId: string;
  summary: string;
  sensitivity: Sensitivity;
  permission: "allowed" | "internal_only" | "confirm_first" | "suppressed";
  sourceIds: string[];
};
```

## 8. 新记忆进入流程

```text
1. Adapter receives a user turn.
2. Adapter sends ObserveRequest to HTC Core.
3. Core classifies speech act, time, candidate objects, sensitivity, and conflicts.
4. Core creates Candidate, not Memory.
5. Workbench Inbox shows the Candidate.
6. User accepts, edits, merges, suppresses, or rejects.
7. Core creates or updates Memory with source lineage.
```

第一版所有候选进入 Inbox。后续可以让低风险事实自动创建，但那是 MVP 之后的策略扩展，且必须可查看和撤回。

## 9. 旧记忆恢复流程

旧记忆恢复不是一次性导入全部历史。

第一版支持三种恢复方式：

1. 用户手动写一段摘要；
2. 用户选择一个导出的会话文件；
3. Adapter 提交当前会话中用户主动重新提起的旧事。

流程：

```text
Import or manual recovery
        ↓
Extract candidates
        ↓
De-identify / minimize source excerpt
        ↓
Merge with existing entities and memories
        ↓
Conflict or uncertainty enters Inbox
        ↓
User confirms or corrects
```

旧记忆恢复必须保留低精度，不补造日期。

示例：

```text
用户说：大概是去年年末或今年年初。
系统保存：2025 年末到 2026 年初，precision=range，confidence=medium。
系统不能保存：2026-01-01。
```

## 10. 多会话冲突处理

冲突类型：

- 同一人物不同写法；
- 同一组织不同别名；
- 同一事件不同日期；
- 某个计划后来取消；
- 某个当前事实后来变成历史事实；
- 用户撤回表达许可。

处理原则：

- 用户明确纠正优先；
- 精确证据覆盖概略投影，但保留来源；
- 旧事实曾经成立时关闭有效期；
- 旧事实从未成立时标记 retracted；
- 无法判断时进入 disputed，不静默选择；
- 对敏感内容采用更严格权限。

Inbox 对冲突的展示应该像：

```text
可能是同一个人：
- 旧写法：A
- 新确认：B
建议：将 A 作为转写错误 alias，规范名改为 B。
```

## 11. Connector 策略

第一版不读取任何产品的私有数据库。

支持顺序：

1. Manual Observation：用户手动输入一段；
2. JSONL / Markdown Import：用户提供导出或粘贴文件；
3. Codex Adapter：由当前会话主动提交 observation；
4. Hermes Adapter；
5. 其它正式导出格式。

不做：

- 直接读取 Codex SQLite；
- 直接读取 ChatGPT / Claude 私有缓存；
- 后台扫描用户磁盘聊天记录；
- 未经用户选择导入历史。

## 12. 第一版验收标准

1. 系统支持一个 User 和至少三个 Conversation。
2. 同一 Memory 可以关联多个 Source。
3. Timeline 只展示 User-level Memory，不按 Conversation 分割。
4. Inbox 能展示来自不同 Conversation 的 Candidate。
5. 用户能确认、编辑、合并、拒绝和删除 Candidate。
6. 用户能对单条 Memory 设置 proactiveExpression=false。
7. Recall Preview 能选择一个 Conversation 并返回 allowed/internal/suppressed 三类结果。
8. 一个会话中的测试句不会创建现实 Memory。
9. 一个会话中的人名纠正能修正另一个会话里已有的 alias。
10. 一个可选建议不会被记成已安排计划。
11. 旧记忆恢复保留时间低精度，不补造具体日期。
12. 删除或撤回表达许可后，新的 RecallPackage 不再包含被禁止主动表达的内容。
13. 不需要读取 Codex 私有 SQLite 即可完成以上流程。
14. 所有候选、记忆和召回项都有 source lineage。
15. Workbench 能导出用户级记忆为 JSON。

## 13. 第一版测试场景

### 场景 A：多会话合并人物

Conversation 1 中出现一个 ASR 错误人名。Conversation 2 中用户纠正写法。Workbench 应显示一个人物实体，旧写法为 alias。

### 场景 B：医疗检查不是长期诊断

Conversation 1 中用户描述一次检查和正常结果。Conversation 2 中谈工作时，Recall Preview 不应主动带出检查细节。

### 场景 C：可选建议不是计划

用户说医生建议“不放心可以做某检查”，但后来明确没做。Memory 状态应为可选建议未安排，不得进入待办。

### 场景 D：旧经历恢复保持低精度

用户恢复一段旧经历，只说“大概去年年末”。系统不得补具体日期。

### 场景 E：同一个人跨会话

多个 Conversation 提到同一工作机会、同一朋友、同一当前公司。Timeline 以用户人生线展示，不按 thread 分裂。

## 14. 推荐工程切片

第一周只做垂直切片：

1. SQLite schema draft；
2. `observe` CLI 接收 JSONL；
3. Candidate Inbox 的静态 Web UI；
4. Memory Detail 编辑权限；
5. Recall Preview 的规则版输出；
6. 用 T01-T09 和本文件场景 A-E 做回归。

先不接真实 Codex 内部数据。先让用户手动提交 observation，证明核心形态和控制感成立。

## 15. 待决策

- 第一版 UI 技术栈是 Next.js 还是更轻的 Vite + React；
- 本地数据库使用 SQLite 还是 PGLite；
- Candidate 是否全部人工确认，还是普通低风险允许自动确认；
- Workbench 是否需要登录，还是本地单用户免登录；
- JSON 导出格式是否先稳定为开发者接口；
- Codex Adapter 是 CLI 命令、Skill，还是 MCP server。

当前建议：第一版使用 Vite + React + SQLite，单用户免登录，所有 Candidate 先进 Inbox，Codex 只通过显式 Adapter 提交 observation。
