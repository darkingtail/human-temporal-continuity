# Human Temporal Continuity

让个人 AI 拥有人类式的记忆能力，并始终理解时间。

> 项目名称为工作名。当前阶段先打磨产品语义与核心边界，不急于绑定某个 Agent、Skill 或存储后端。

## 它是什么

Human Temporal Continuity（HTC）是一个可复用的“人类式记忆核心”：它让 AI 理解同一个人在时间中的经历、变化、意图和意义，并以选择性、可纠正、克制且合时宜的方式记住和想起。

它不是重新造陪伴聊天产品，而是定义并实现这些产品都需要的“人类式记忆核心”。

第一参考体验是一个人与 AI 的长期、多会话聊天：

- 知道“明天再做”当时指哪一天；
- 不把计划日期过去误认为事情已经完成；
- 记得过去经历对现在的影响，但不乱下心理结论；
- 不把一次难过固化成永久人格标签；
- 相关的敏感记忆也不一定主动说出口；
- 允许用户查看、纠正、降级和删除记忆。

## 产品层次

1. 人类记忆语义；
2. 可复用 Human Memory Core；
3. 薄聊天适配器与个人参考体验；
4. 经过真实验证后再提炼适配规范和一致性测试。

## 它不是什么

- 不是新的陪伴聊天应用；
- 不是一个大而全的 Skill；
- 不是另一套向量数据库；
- 不是新的 Agent 框架；
- 不是聊天记录永久归档系统；
- 不是提醒器或日历本身；
- 不是优先建设的 memory CRUD 或数据交换协议。

Skill、Agent 插件、MCP Server、存储引擎和调度器都可以承载或接入 HTC，但不等于 HTC 本身。

## 文档

- [HTC 产品历程：从时间感到人类式记忆核心](docs/htc-journey.md)
- [产品定义](docs/product-definition.md)
- [Memory Workbench MVP](docs/memory-workbench-mvp.md)
- [Bootstrap 与记忆恢复](docs/bootstrap-memory-recovery.md)
- [Codex Adapter MVP](docs/codex-adapter-mvp.md)
- [2026 行业扫描与旧分析对照](docs/industry-scan-gstack-2026-07-17.md)
- [竞品与既有方案分析](docs/competitive-analysis.md)

## 本地原型

```bash
npm install
npm run dev
```

仓库现在包含一条贯通的本地产品链：Python Silent Core + SQLite、Codex Hooks / STDIO MCP Adapter，以及读取同一数据库的 Vite Memory Workbench。

## 当前状态

`Silent Core MVP / Bootstrap Recovery / Codex Adapter MVP / Local Workbench MVP`

Silent Core 已实现 `observe -> candidate -> decide -> memory -> recall -> explain`，并通过项目级 Codex Hook 在回答前注入安全召回上下文、通过 MCP 提供显式召回。Workbench 已通过 loopback API 读取同一份真实 Core 数据，可审核 Candidate、查看来源与治理解释、纠正或撤回 Memory、关闭主动提及并设置用户级跨会话权限。

Workbench 的 Recall Preview 还能输入一句模拟消息，分别展示允许用于回答、只作内部引导、需要先确认的记忆，以及 Adapter 最终实际获得的安全投影。

Workbench 还提供来源会话审计：列出 HTC 自己已知的 Observation / Adapter Event
会话，并展示它们贡献的 Candidate、Memory 和最小化来源片段。它不会读取 Codex
等宿主产品的私有聊天数据库，也不会向界面返回 Adapter Event payload。

本地启动方式：

```powershell
cd core
uv run htc-workbench-api
# 另开终端，从仓库根目录运行
pnpm dev
```
