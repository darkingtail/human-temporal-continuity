# 竞品与既有方案分析

> 调研日期：2026-07-16
>
> 目的：判断“具有人类时间概念的个人 AI 记忆规范”是否已有完整重复，并确定项目边界
>
> 方法：优先阅读项目 README、官方文档、论文摘要和公开规范；不同成熟度、不同层级的项目不直接用单一排行榜比较

## 1. 结论摘要

目前没有发现一个成熟项目完整覆盖本项目的全部目标，但几乎每个组成部分都有明确先例。

最接近的方案分别占据不同位置：

- **AMP（smriti-memcore）** 最接近可互操作的记忆服务协议。
- **Graphiti** 最接近“事实随时间变化”的时态真值模型。
- **MemoryBank** 最接近受遗忘曲线和重要性影响的类人记忆。
- **Mem0** 最接近可直接使用、并正在强化时间检索的通用记忆层。
- **Letta** 最接近以持久状态和可编辑记忆为核心的 Agent 架构。
- **Honcho** 最接近持续理解“会变化的人、关系、群体和项目”的用户建模层。
- **MemOS** 最接近包含存储、纠正、调度、策略与 Skill 演化的记忆操作系统。
- **Hermes Agent** 最接近“在使用中不断学习、生成并改进 Skill 的完整 Agent 产品”。

本项目仍有独立价值，但定位必须准确：

> 不再做一个底层 memory CRUD 协议，而是定义一套人本的个人记忆与时间连续性语义规范，并允许映射到 AMP、Mem0、Graphiti、MemOS 或本地存储。

## 2. 为什么需要分层比较

“AI 记忆”至少包含六个不同问题：

| 层级 | 解决的问题 | 代表方案 |
| --- | --- | --- |
| 传输与工具调用 | Agent 如何调用外部能力 | MCP |
| 记忆服务协议 | 如何统一 encode、recall、forget、export 等接口 | AMP |
| 存储与检索运行时 | 记忆如何保存、索引、召回和扩展 | Mem0、MemOS、Letta、Honcho |
| 时间真值模型 | 事实何时有效、如何被新事实替代 | Graphiti |
| 类人认知策略 | 重要性、遗忘、反思、意义和个性适应 | MemoryBank、Generative Agents、A-MEM |
| Agent 学习与适配 | 如何从经验形成程序性能力或 Skill | Hermes、MemOS、Letta |

HTC 主要处于“时间真值模型 + 类人认知策略 + 规范化行为”之间，并为上下两层定义可验证的约束。

## 3. 总体比较矩阵

| 项目 | 类型 | 最强能力 | 与 HTC 的重合 | 主要缺口或差异 |
| --- | --- | --- | --- | --- |
| AMP（smriti-memcore） | 开放服务协议 | REST/MCP、Schema、导入导出、一致性测试、生命周期操作 | 存取、遗忘、压缩、TTL、置信度、固定 | 不定义丰富的人类时间表达、前瞻性事项和表达适宜性 |
| Graphiti | 时态知识图谱 | 双时间、有效区间、来源、事实替代且保留历史 | 当前/历史事实、纠正、时间检索 | 不负责自然遗忘、意义、计划结果未知、用户治理行为 |
| MemoryBank | 研究型记忆机制 | 艾宾浩斯遗忘曲线、重要性、强化、个性适应 | 类人遗忘、长期关系理解 | 不是互操作规范；时间与前瞻性事项较弱 |
| Mem0 | 产品化记忆层 | 多层记忆、SDK/API、生产集成、时间感知检索 | 个性化、跨会话、当前/过去/未来计划检索 | 语义和行为主要由产品实现决定，不是跨实现规范 |
| Letta | 有状态 Agent 平台 | Agent 自编辑核心记忆、持久状态、上下文管理 | 长期 Agent、记忆可编辑、持续学习 | 不以人类时间连续性的一致性规范为中心 |
| LangGraph Memory | Agent 框架能力 | semantic/episodic/procedural 分类、短期/长期写入 | 记忆分类、前台/后台维护 | 偏框架实践，不定义跨 Agent 的时间与治理语义 |
| Generative Agents | 研究架构 | 记忆流、重要性、近因、相关性、反思、计划 | 重要性与反思、计划行为 | 偏模拟角色；完整记录经历，与克制个人记忆不同 |
| A-MEM | 研究型 Agentic Memory | 动态链接、Zettelkasten、自组织与记忆演化 | 新记忆触发旧记忆更新、意义关联 | 时间有效性、前瞻性状态和隐私治理不是重点 |
| Honcho | 用户/实体建模基础设施 | 对变化的人、Agent、群体、项目持续建模和推理 | 长期用户理解、关系随时间变化 | 不是人类时间与遗忘行为规范；偏服务和推理层 |
| MemOS | 记忆操作系统 | 多模态、图记忆、纠正、调度、策略和 Skill 演化 | 生命周期、纠正、Agent 成长、Hermes 集成 | 范围更宽，缺少 HTC 所强调的规范化时间表达与非侵入行为 |
| Hermes Agent | 自进化 Agent | 闭环学习、自动创建/改进 Skill、会话搜索、用户模型 | 程序性记忆、持续学习、跨会话用户理解 | 是 Agent 产品，不是可移植记忆语义；可成为 HTC 适配目标 |
| WAMP | 浏览器内存协议 | 网站与浏览器扩展间的标准 API、权限与多提供方 | 协议优先、用户控制、可移植 | 只面向浏览上下文，时间字段较基础 |
| AMP（mmorris35） | 另一套 Agent Memory Protocol | 最小公分母式存储/搜索协议、本地优先 | 协议中立和跨后端 | 名称与另一 AMP 冲突；语义层较薄 |
| PMP（Jaghadish） | 本地个人记忆系统 | 本地优先、MCP daemon、捕获与召回 | 个人记忆、本地化 | 已占用 Personal Memory Protocol 名称；目标更像具体产品 |

## 4. 最接近的协议竞争者：AMP

项目：[smriti-memcore/amp](https://github.com/smriti-memcore/amp)

### 4.1 它已经解决什么

AMP 自称 Agent Memory Protocol，是一套面向 AI Agent 持久记忆的开放规范。其公开材料显示：

- 同时提供 REST 与 MCP 两种交付通道；
- 使用共享 JSON Schema 和 OpenAPI 合约；
- 定义 `encode`、`recall`、`forget`、`stats`、`consolidate`、`pin`、`export`、`import` 等操作；
- 提供组织、应用、用户、会话、Agent、群组和工作区等多维作用域；
- 预留 `ttl`、`confidence`、`entities`、`relations`、`categories`、`summary` 等元数据；
- 定义 MXF 交换格式和冲突策略；
- 区分 Core 与 Full 一致性等级；
- 提供可运行的一致性测试套件；
- 将 spaced decay、后台压缩和归档纳入高级生命周期。

这意味着：如果 HTC 重新定义一套“存一条记忆、搜一条记忆、删一条记忆”的接口，会与 AMP 高度重复，而且很难在互操作性和成熟度上形成优势。

### 4.2 它没有完整解决什么

从当前公开规范看，AMP 更关心服务接口与后端互操作，而不是以下高层行为：

- “明天”如何绑定原始锚点并随当前日期重新表述；
- 计划时间已过但结果尚未确认时的规范状态；
- `event_time`、`learned_at`、`expected_at`、有效区间之间的语义区别；
- 用户因系统遗忘而失望时，如何升级重要性；
- 事情对用户的意义如何保存且避免过度心理推断；
- 召回相关性与“是否适合主动说出口”如何分离；
- 不同 Agent 对上述场景应表现出的统一自然语言行为。

### 4.3 对 HTC 的启示

推荐关系不是替代 AMP，而是叠加：

```text
MCP
  → 工具传输

AMP 或其他后端协议
  → 记忆存储、检索和交换互操作

HTC
  → 人本记忆、时间连续性和行为一致性语义
```

HTC 可以定义一组命名空间扩展字段和到 AMP 元数据的映射，但不应复制 AMP 的核心动词。

## 5. 最接近的时间模型：Graphiti

- 项目：[getzep/graphiti](https://github.com/getzep/graphiti)
- 论文：[Zep: A Temporal Knowledge Graph Architecture for Agent Memory](https://arxiv.org/abs/2501.13956)

### 5.1 它已经解决什么

Graphiti 将记忆建模为时态上下文图：

- 实体、关系和事实会随交互持续变化；
- 每个事实具有有效窗口；
- 新事实可以使旧事实失效，而不是删除历史；
- 保留信息来源；
- 支持“现在什么为真”和“过去某时什么为真”的查询；
- README 明确描述 bi-temporal tracking；
- 通过语义、关键词和图遍历进行混合检索；
- 提供 MCP Server。

这与 HTC 的纠正、有效区间和历史事实需求高度契合。HTC 没有必要重新发明时态知识图谱。

### 5.2 它没有完整解决什么

- 计划与事实的本体区别；
- `expected_at` 已过、但 `outcome` 未知的前瞻性记忆；
- 原始相对时间表达及其锚点；
- 按重要性和意义进行的自然遗忘；
- 用户失望等关系信号；
- 敏感记忆的写入确认和表达适宜性；
- 面向多个 Agent 的行为一致性测试。

### 5.3 对 HTC 的启示

Graphiti 可以作为强后端或参考时间模型。HTC 应吸收“有效时间 + 得知时间 + 来源 + 替代但不抹除历史”的思想，同时补上个人助手中的计划、意义、遗忘和治理语义。

## 6. 最接近的类人遗忘：MemoryBank

论文：[MemoryBank: Enhancing Large Language Models with Long-Term Memory](https://arxiv.org/abs/2305.10250)

### 6.1 它已经解决什么

MemoryBank 面向长期陪伴场景，明确提出：

- 从历史交互召回相关记忆；
- 持续更新记忆；
- 综合历史信息理解并适应用户个性；
- 借鉴艾宾浩斯遗忘曲线；
- 根据时间流逝和记忆相对重要性进行遗忘与强化；
- 追求更接近人的选择性记忆行为。

这证明“遗忘不是失败，而是记忆机制的一部分”已有直接研究基础。

### 6.2 它没有完整解决什么

- 它是一种研究机制，不是跨产品互操作协议；
- 没有完整覆盖事实有效期和纠正历史；
- 前瞻性事项和结果未知不是核心；
- 用户查看、降级、删除和敏感写入等治理要求较弱；
- 不提供 Agent 中立的一致性套件。

### 6.3 对 HTC 的启示

HTC 可以借鉴“时间 × 重要性 × 强化”的衰减思想，但不应把单一遗忘曲线写成强制算法。规范更适合约束可观察行为，把具体曲线留给实现。

## 7. 通用记忆产品：Mem0

项目：[mem0ai/mem0](https://github.com/mem0ai/mem0)

### 7.1 它已经解决什么

Mem0 是成熟的通用记忆层，强调：

- 用户、会话和 Agent 多层记忆；
- 长期个性化与跨会话使用；
- SDK、API、自托管与托管形态；
- 与多种 Agent 和 Skill 工作流集成；
- 2026 年公开的新记忆算法加入 temporal reasoning；
- 时间感知检索可以面向当前状态、过去事件和未来计划选择正确的日期实例。

Mem0 已经进入 HTC 所关心的时间检索范围，因此不能把“有时间字段”或“能搜未来计划”本身当成独特卖点。

### 7.2 仍然存在的空间

HTC 的差异应放在可验证语义而非单一产品能力：

- 明确区分预期与发生；
- 明确结果未知；
- 保存相对时间原文、锚点、精度和时区；
- 定义纠正后旧版本不得复发；
- 定义非侵入式表达；
- 允许 Mem0 和其他后端接受同一套一致性测试。

## 8. Stateful Agent：Letta 与 LangGraph

- 项目：[letta-ai/letta](https://github.com/letta-ai/letta)
- 文档：[Letta Stateful Agents](https://docs.letta.com/guides/core-concepts/stateful-agents)
- 文档：[LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory)

### 8.1 Letta

Letta 将持久状态和高级记忆作为 Agent 核心能力，Agent 可以管理自身记忆块，并在持续交互中学习和改进。它证明记忆不只是外部检索服务，也可以是 Agent 可主动维护的内部状态。

与 HTC 的关系：

- Letta 可以实现 HTC Adapter；
- HTC 可以约束 Letta 中哪些内容应写入、如何纠正、如何处理时间；
- Letta 的上下文工程和自编辑记忆不等于跨 Agent 的语义标准。

### 8.2 LangGraph

LangGraph 文档使用 semantic、episodic、procedural 等记忆分类，并区分在请求前台或后台维护长期记忆。这为 HTC 的“事实、经历、做事方式”分类和异步压缩提供了实践参考。

但 LangGraph 主要提供框架级构建方式，不负责定义个人助手必须遵守的时间、隐私和自然语言表达行为。

## 9. 认知架构研究：Generative Agents 与 A-MEM

### 9.1 Generative Agents

论文：[Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)

该研究提出记忆流、动态检索、反思和计划。经典检索思想综合了近因、重要性和相关性，并通过更高层反思帮助 Agent 形成长期行为。

与 HTC 的重要区别是：Generative Agents 为了模拟可信角色，保存较完整的经历记录；HTC 面向真实个人用户，默认应少记、可控，并对敏感信息和非侵入表达提出更高要求。

### 9.2 A-MEM

- 论文：[A-MEM: Agentic Memory for LLM Agents](https://arxiv.org/abs/2502.12110)
- 实现：[WujiangXu/A-mem](https://github.com/WujiangXu/A-mem)

A-MEM 借鉴 Zettelkasten，让新记忆生成上下文、关键词和标签，并动态寻找历史关联。新记忆还可以触发旧记忆的上下文表征和属性更新，使记忆网络持续演化。

这与 HTC 的“记忆不是静态事实列表”一致。但 A-MEM 更关注自组织和关联质量，HTC 更关注时间真值、前瞻状态、纠正、遗忘、隐私和跨实现一致行为。

## 10. 用户建模基础设施：Honcho

项目：[plastic-labs/honcho](https://github.com/plastic-labs/honcho)

Honcho 的定位是帮助有状态 Agent 理解会随时间变化的人、Agent、群体、项目和想法。其公开材料强调：

- 从对话和事件中提取结论，而非只匹配文本块；
- 以 Peer 为中心建模用户、Agent、群体和项目；
- 对这些实体随时间变化进行持续理解；
- 提供 SDK、MCP 和多 Agent 集成；
- 已被 Hermes 用于 dialectic user modeling。

Honcho 与 HTC 在“长期理解一个变化中的人”上高度相关。差异在于：Honcho 是具体推理与记忆基础设施，HTC 是可用于约束 Honcho 或其他后端行为的规范。

HTC 不应与 Honcho 竞争“谁更会建立用户模型”，而应定义用户模型在时间、来源、敏感性、纠正和表达时必须遵循的边界。

## 11. 记忆操作系统：MemOS

项目：[MemTensor/MemOS](https://github.com/MemTensor/MemOS)

MemOS 的范围比一般记忆库更宽：

- 统一添加、检索、编辑和删除 API；
- 图结构、可检查和可编辑记忆；
- 文本、图片、工具轨迹和 Persona 多模态记忆；
- 多个 Memory Cube 的隔离与组合；
- 通过 MemScheduler 异步处理；
- 支持自然语言反馈、纠正、补充和替换；
- 将轨迹、策略、世界模型和结晶 Skill 组织成多层演化；
- 为 Hermes Agent 和 OpenClaw 提供本地记忆插件；
- 本地插件包含 FTS5 + vector、去重、任务摘要、Skill 演化和多 Agent 协作。

MemOS 与本项目的实现愿景重合度很高，尤其是纠正、调度、Agent 成长和 Skill 演化。

但两者仍不是同一层：

- MemOS 是 Memory OS 和具体运行时；
- HTC 是对“什么状态才算正确、时间应如何解释、何时不应说出口”的规范；
- HTC 可以在 MemOS 上实现，也可以用于测试 MemOS 插件是否符合个人连续性要求。

战略上应重点关注 MemOS 的演化速度，因为它最可能继续向 HTC 的语义范围扩展。

## 12. Hermes Agent 与本项目的关系

- 项目：[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- 文档：[Hermes Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)
- 文档：[Hermes Skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)

### 12.1 Hermes 已经具备什么

Hermes 将自己定义为 self-improving AI agent，公开 README 描述了一个闭环学习系统：

- Agent 主动整理记忆并接受周期性 nudges；
- 完成复杂任务后可以自动创建 Skill；
- Skill 在使用中继续改进；
- 使用 FTS5 搜索历史会话，并由 LLM 总结跨会话内容；
- 使用 Honcho 建立更深的用户模型；
- 兼容 agentskills.io；
- 能迁移既有 MEMORY.md、USER.md 和 Skill；
- 可接入 MemOS 等记忆插件。

### 12.2 它和 HTC 是否重复

有明显关联，但不重复。

Hermes 解决的是：

> 一个 Agent 如何从经验中持续学习、形成程序性能力，并在不同会话中更了解用户。

HTC 解决的是：

> 无论哪个 Agent、Skill 或后端，个人记忆和时间推理怎样才算语义正确、克制、可纠正和可验证。

Hermes 的“不断进化”主要覆盖程序性记忆与 Agent 自我改进；HTC 的独特重点是个人事实、经历、计划、意义和时间流逝。

### 12.3 最合适的合作方式

Hermes 应被视为首批参考适配目标之一：

- Hermes Skill 负责触发 HTC 操作；
- Hermes Memory 或 MemOS/Honcho 负责实际存储与检索；
- HTC Runtime 负责时间解析、状态转换、纠正和表达过滤；
- HTC 一致性测试验证 Hermes 是否会把过期计划误报为已完成、是否会复用旧事实等。

换句话说，Hermes 可以“不断进化”，HTC 负责让它在进化过程中不丢失时间和个人记忆的语义边界。

## 13. 其他协议项目与命名冲突

### 13.1 另一套 Agent Memory Protocol

项目：[mmorris35/agent-memory-protocol](https://github.com/mmorris35/agent-memory-protocol)

该项目同样使用 AMP 名称，目标是为持久记忆建立最小公分母式接口，强调本地优先、跨后端和 MCP 工具。它进一步证明“Agent Memory Protocol / AMP”命名和底层协议方向已经拥挤。

### 13.2 Web Agent Memory Protocol

项目：[web-agent-memory/web-agent-memory-protocol](https://github.com/web-agent-memory/web-agent-memory-protocol)

WAMP 是浏览器 API 规范，通过 `window.agentMemory` 连接网站和记忆扩展，强调逐站点授权、多提供方、撤销权限和导入导出。它的范围是浏览行为上下文，并不覆盖完整个人连续性，但其权限设计值得参考。

### 13.3 Personal Memory Protocol 已被使用

项目：[Jaghadish/pmp](https://github.com/Jaghadish/pmp)

该项目已经使用“PMP - Personal Memory Protocol”，定位为本地优先的个人记忆系统，并提供 MCP daemon 和 Claude Desktop 集成。

此外，公开网络中还曾出现“federated personal memory protocol”相关表述。因此不建议本项目使用 `Personal Memory Protocol` 或 `PMP` 作为正式名称。

## 14. 尚未被完整覆盖的差异化空间

### 14.1 前瞻性记忆是一等对象

多数系统可以保存未来日期，但很少把以下状态作为规范核心：

```text
planned / active / waiting / paused / completed / cancelled
overdue + outcome_unknown
```

尤其重要的是：

> 时间过去不代表事件发生。

### 14.2 相对时间的完整锚定

不仅保存解析结果，还保存：

- 原始表达；
- 锚点；
- 绝对时间或范围；
- 时区；
- 精度与不确定性；
- 面向当前时刻的重新表达。

### 14.3 多种时间不能混为一个 timestamp

HTC 明确区分：

- 事件时间；
- 得知时间；
- 预期时间；
- 事实有效区间；
- 记录和更新时间；
- 当前结果状态。

### 14.4 记忆意义

HTC 不只保存“发生了什么”，还允许保存“为什么它会影响以后理解用户”，同时禁止无依据的心理推断。

### 14.5 遗忘失望是关系信号

用户对遗忘表示诧异或失望时，不只是临时修正答案，还应触发该记忆重要性和写入策略的复核。

### 14.6 非侵入式召回

“检索相关”不等于“适合主动说出”。这一行为边界在底层记忆产品中通常不是一等规范。

### 14.7 规范化用户治理

查看、更正、降级、删除、敏感写入确认、推断标识和禁止过度心理分析，应成为一致性要求而非某个产品的可选 UI。

### 14.8 行为一致性测试

HTC 的真正护城河不应只是字段表，而应是能跨 Codex、Hermes、Claude 和不同后端执行的场景测试。

## 15. 推荐产品策略

### 15.1 不推荐：再做一个底层记忆 CRUD 协议

原因：

- AMP 已经定义了核心动词、Schema、作用域、交换格式和一致性级别；
- Mem0、MemOS、Graphiti 等已有成熟实现；
- 新协议很难仅凭接口命名形成采用优势；
- 会稀释本项目真正独特的时间与人本语义。

### 15.2 可选：AMP 专用扩展 Profile

优点：

- 快速利用现有协议和一致性基础；
- 更容易展示互操作；
- 可以集中精力定义 `htc.*` 语义字段。

缺点：

- 项目会被 AMP 的演化和采用情况绑定；
- Graphiti、MemOS 或纯本地实现需要额外适配；
- 容易让外界误解 HTC 只是 AMP 插件。

### 15.3 推荐：后端中立规范 + 官方 AMP 映射

核心规范独立定义可观察行为和规范化对象，同时提供：

- `HTC Core Semantics`；
- `HTC Conformance Scenarios`；
- `HTC Mapping for AMP`；
- `HTC Mapping for Temporal Graphs`；
- 一个最小本地参考运行时；
- Codex 与 Hermes 薄适配器。

这样既保持独立性，也不重复建设底层基础设施。

## 16. 可能的扩展字段

若映射到支持命名空间元数据的后端，可以考虑：

```yaml
htc.event_time:
htc.learned_at:
htc.anchor_time:
htc.expected_at:
htc.valid_from:
htc.valid_to:
htc.time_precision:
htc.timezone:
htc.original_expression:
htc.status:
htc.outcome:
htc.meaning:
htc.importance:
htc.sensitivity:
htc.next_review_at:
htc.supersedes:
```

字段必须服务于规范行为，而不是为了显得模型复杂。

## 17. 风险

### 17.1 大型记忆产品快速覆盖差异

Mem0、MemOS、Graphiti 和 Honcho 都在快速演进，可能继续加入前瞻性记忆、纠正或用户治理功能。

应对：把价值放在供应商中立的一致性语义和测试，而不是某个单点特性。

### 17.2 规范过重

如果一开始定义过多字段和状态，实现者会放弃接入。

应对：设置 Core 与 Extended 两级。Core 只保留时间、状态、纠正、来源和治理底线。

### 17.3 “类人”导致过度心理建模

记住意义可能滑向未经同意的人格画像或心理推断。

应对：明确证据、置信度、敏感性和用户确认规则；默认禁止诊断性推断。

### 17.4 遗忘与可追溯冲突

逻辑遗忘、归档和物理删除的目标不同。

应对：规范中明确区分召回衰减、归档、替代和删除，并要求实现说明其保证等级。

### 17.5 Agent 适配器重新吞掉核心规范

如果实现最终只存在于一个 Skill，项目会退化回单 Agent 脚本。

应对：先发布独立 Schema 和一致性场景；Skill 只调用核心运行时或映射规范。

## 18. 最终判断

这个想法不是“互联网上完全没人做过”的空白领域，也不是某个现有项目的简单复制。

更准确的判断是：

- 存储、召回、遗忘、时间图谱、用户建模、Skill 演化等组件都已有强方案；
- 目前缺少一套把这些能力组合成“个人 AI 的时间连续性行为”，并能跨 Agent 验证的中立规范；
- 本项目最值得做的部分是语义、边界和一致性测试；
- 运行时和 Skill 应当是证明规范可实现的参考产品，而不是项目本体。

建议采用以下对外表述：

> Human Temporal Continuity 是一套规范个人 AI 如何理解、纠正、遗忘和召回个人记忆，并在时间流逝后保持事实、计划和表达一致性的开放语义标准。

## 19. 主要资料

### 协议与产品

- [Agent Memory Protocol — smriti-memcore/amp](https://github.com/smriti-memcore/amp)
- [Agent Memory Protocol — mmorris35/agent-memory-protocol](https://github.com/mmorris35/agent-memory-protocol)
- [Web Agent Memory Protocol](https://github.com/web-agent-memory/web-agent-memory-protocol)
- [PMP — Personal Memory Protocol](https://github.com/Jaghadish/pmp)
- [Graphiti](https://github.com/getzep/graphiti)
- [Mem0](https://github.com/mem0ai/mem0)
- [Letta](https://github.com/letta-ai/letta)
- [LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory)
- [Honcho](https://github.com/plastic-labs/honcho)
- [MemOS](https://github.com/MemTensor/MemOS)
- [Hermes Agent](https://github.com/NousResearch/hermes-agent)

### 论文

- [MemoryBank: Enhancing Large Language Models with Long-Term Memory](https://arxiv.org/abs/2305.10250)
- [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)
- [A-MEM: Agentic Memory for LLM Agents](https://arxiv.org/abs/2502.12110)
- [Zep: A Temporal Knowledge Graph Architecture for Agent Memory](https://arxiv.org/abs/2501.13956)
