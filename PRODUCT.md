# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

HTC 首先服务于长期与 AI 交流的个人用户。他们会在不同时间、不同工具和多条会话中谈论工作、关系、健康、计划、感受和过去经历，希望 AI 面对新的会话时仍能理解“这是同一个人”，而不是把每条线程当成互不相干的身份。

首位真实用户是项目创建者本人。第一阶段以个人连续使用和真实跨会话轨迹验证产品，而不是先为团队协作或大众市场扩展功能。

## Product Purpose

HTC 让 AI 理解同一个人在时间中的经历、关系、事实、意图、变化和意义，并以选择性、可纠正、克制且合时宜的方式记住和召回这些内容。

成功不是“存下更多聊天记录”，而是让用户在新的 AI 会话中感到自己被持续理解，同时始终知道 AI 记住了什么，并能纠正、限制、隐藏或删除这些记忆。

## Positioning

HTC 是来源无关的人类式记忆核心，不是新的聊天产品、聊天记录浏览器、向量数据库、Agent 框架或某个工具的专用 Skill。

它以用户为记忆所有者，以会话为来源证据，通过显式的时间语义、状态变化、来源追溯、表达权限和用户治理，把分散会话沉淀为同一个人的连续记忆。相邻的聊天产品或通用记忆后端不能只靠保存摘要来等价实现这一机制。

## Operating Context

首个产品形态是 **HTC Local Memory Hub**：运行在个人电脑上的本地记忆中枢，包含本地核心、持久化存储、可视化 Memory Workbench，以及连接不同 AI 工具的 Adapter / Importer。

典型流程：

1. Codex、Claude、ChatGPT、其他聊天工具或手动记录产生 observation。
2. 用户通过显式 Adapter、导入文件或手动输入将 observation 提交给 HTC。
3. HTC 解析话语作用、时间、候选记忆、敏感度和潜在冲突。
4. 新内容先进入 Candidate Inbox，由用户确认、修改、合并、抑制或拒绝。
5. 已治理的用户级记忆进入 Timeline，并按当前会话用途生成短期 Recall Package。
6. 用户通过 Workbench 查看来源、纠正状态、限制主动表达或删除记忆。

Workbench 是 HTC 的治理界面，不等于 HTC 本身。“蜿蜒的路”应表达真实的用户记忆 Timeline，而不是作为与产品割裂的营销首页。

## Capabilities and Constraints

- 首版为单用户、本地优先，不要求登录、云同步或团队协作。
- 当前 Vite + React + TypeScript 工程是产品形态原型，不代表 HTC 是纯前端应用。
- 首版实现应包含本地核心服务和 SQLite 或等价本地存储；具体后端结构尚待工程设计。
- 首个接入渠道可以是 Codex Adapter，但核心不得依赖 Codex。
- 外部工具只能通过显式 Adapter、Importer 或用户操作提交 observation。
- 不读取 Codex、ChatGPT、Claude 等产品的私有 SQLite、IndexedDB 或内部缓存。
- 不在后台偷偷扫描或全量导入用户历史会话。
- Conversation 是来源容器；Memory 归属于 User，而不是某条会话。
- 新候选默认进入 Inbox；敏感内容必须最小化，并默认禁止主动表达。
- Recall Package 必须用途绑定、短期有效，不能跨话题无限复用。
- 计划、假设、引用、测试和角色扮演不能静默变成已发生的现实记忆。
- 时间不确定时保留原始精度，不补造日期；计划日期过去不等于事情已经完成。
- 桌面封装可在本地 Web 形态验证后考虑，Tauri 或其他方案尚未决定。
- HTC 不进行心理诊断，不把短期情绪固化为永久人格标签。

## Brand Commitments

- 当前工作名为 **Human Temporal Continuity（HTC）**，名称尚未最终确定。
- 核心命题：**线程很多，但人只有一个。HTC 的产品边界是用户级记忆，不是会话级记忆。**
- 产品必须让用户感到“被持续理解”，而不是“被监控”。
- 正常聊天应自然、克制，不逐轮播报记忆字段、置信度或内部机制。

## Evidence on Hand

- 产品定义与记忆语义：[docs/product-definition.md](docs/product-definition.md)
- Memory Workbench MVP：[docs/memory-workbench-mvp.md](docs/memory-workbench-mvp.md)
- 多日参考轨迹：[docs/multi-day-reference-traces-2026-07.md](docs/multi-day-reference-traces-2026-07.md)
- 行业扫描：[docs/industry-scan-gstack-2026-07-17.md](docs/industry-scan-gstack-2026-07-17.md)
- 当前可运行的静态原型：[src/App.tsx](src/App.tsx)

当前没有已验证的客户案例、公开用户数据、商业指标、定价或市场承诺。未来设计不得编造这些证据。

## Product Principles

1. **用户连续性高于线程边界。** 线程很多，但产品始终围绕同一个人的生活上下文组织记忆。
2. **控制感高于记忆炫技。** 用户能够查看、纠正、限制和删除；系统不靠突兀复述隐私来证明自己记得。
3. **时间是记忆的一部分。** 区分发生时间、观察时间、计划时间、有效期和未知结果，不把未来意图误写成既成事实。
4. **证据与不确定性必须保留。** 记忆有来源、状态和精度；纠正更新当前投影，但历史证据仍可追溯。
5. **内部相关不等于允许表达。** 召回必须经过用途、敏感度和用户权限门控，克制是核心能力而不是缺失能力。
