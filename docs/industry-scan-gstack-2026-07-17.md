# HTC 2026 行业盲扫与旧分析对照

日期：2026-07-17  
方法：GStack `/office-hours` 的 Search Before Building 与 premise challenge 逻辑  
状态：扫描与对照完成

## 1. 方法与独立性边界

本轮先不读取 `docs/competitive-analysis.md`，只使用截至 2026-07-17 可访问的一手来源：论文、官方仓库、云厂商文档和项目规范。先形成并写下独立结论，再打开旧文档逐项比较，避免旧分类和旧结论引导新扫描。

扫描问题不是“谁也在做 memory”，而是：

1. 哪些能力已经成为普通产品或云平台能力；
2. 哪些能力已经有公开 benchmark；
3. 哪些能力已经有协议和 conformance suite；
4. 哪些跨系统语义仍缺少可执行、供应商中立的约束。

证据分三层：

- 强证据：同行评审论文、官方规范、官方文档、可运行的公开测试套件；
- 中等证据：官方仓库 README、公开 leaderboard 和可复现实验代码；
- 弱证据：厂商自报分数、低采用量的新协议提案。弱证据只用于发现方向，不单独支撑市场结论。

## 2. 独立扫描结论

### 2.1 结论摘要

HTC 仍有空间，但空间比“通用 Agent Memory 标准”窄得多。

2026 年已经同时存在：

- 长期对话记忆、时间推理、知识更新、冲突解决和超长上下文 benchmark；
- 面向多会话 agentic task 的经验记忆 benchmark；
- 专门测试未来意图执行的 prospective-memory benchmark；
- 云厂商提供的抽取、合并、结构化 profile、TTL、revision、remember/forget 和 procedural memory；
- 多个名为 AMP/OAMP/WAMP 的记忆协议，其中至少两个已经提供 schema、参考实现和 compliance/conformance tests；
- Mem0、MemOS、Graphiti/Zep 等成熟或快速增长的记忆基础设施；
- Hermes Agent 内置的持久记忆、用户建模、技能演化与定时自动化。

因此 HTC 不能以以下内容作为核心新颖性：

- memory CRUD 或统一 API；
- schema、TTL、namespace、profile、revision、consolidation；
- temporal retrieval 或 temporal knowledge graph；
- 单纯的长期回忆 benchmark；
- 单纯的 prospective-memory benchmark；
- 泛化的“记忆协议”或“首个合规套件”。

HTC 尚可形成差异化的方向是：

> 一个位于 agent runtime 与任意 memory backend/protocol 之上的、供应商中立的可执行语义合规层，联合验证时间事实、未来意图生命周期、修正与撤销、用户治理命令，以及在回答或行动时的适当表达。

这不是存储协议，而是行为契约。它可以把 AMP、OAMP、Mem0、MemOS、Graphiti、云 Memory 和文件型 memory 当作被测实现或适配目标。

### 2.2 Benchmark 已从“回忆”扩展到“经验、行动和未来意图”

| 项目 | 已覆盖能力 | 对 HTC 的含义 |
|---|---|---|
| LoCoMo | 长期对话 QA、事件总结、跨 session 因果与时间联系 | 长期对话回忆不是空白领域 |
| LongMemEval | temporal reasoning、knowledge update、multi-session、abstention | 时间推理和更新已有成熟基线 |
| MemoryAgentBench | 增量多轮注入、EventQA、FactConsolidation、准确检索与 test-time learning | “逐步形成记忆”已有专门评测 |
| BEAM | 最长 10M tokens；十类能力含 temporal reasoning、event ordering、contradiction resolution | 规模、矛盾和时间均已有公开 benchmark |
| LongMemEval-V2 | 最多 115M tokens、500 条轨迹；动态状态、workflow、环境陷阱、premise awareness，并计入 latency | 记忆评测已进入真实 agent 经验与操作环境 |
| MemoryArena | 多 session、相互依赖的 agentic tasks；记忆必须影响后续行动 | 单纯 recall 高分不再代表 agent memory 有效 |
| PM-Bench | 七日模拟；延迟意图、事件触发、时间触发、环境监控；最佳 GPT-5.4 agent 仅 65.1% F1 | prospective memory 是明确且仍未解决的类别，但 HTC 不能再宣称它无人评测 |
| OmniMemEval | 统一 adapter 评测 memory backend，并评测装有 memory plugin 的 agent runtime | “同一套 harness 比较多个后端/插件”也已有人执行 |
| MemSyco-Bench | 检查记忆何时应影响决策、适用 scope、与客观证据冲突、更新和有效个性化 | “适当使用记忆”已有直接 benchmark；HTC 不能把它作为无人涉及的单点 |
| A-TMA / LTP | current、historical、transition state 混杂导致的 ghost memory，并拆分 bank、retrieval、answer 三层失败 | 当前/历史事实与纠正复发已有近邻工作；HTC 需强调联合 intention/governance 与跨实现合规 |
| MemLeak | 删除文本后，相关文本、图片或派生表示仍可恢复被忘记事实 | `forget` 必须覆盖派生和多模态残留并非 HTC 独有，但可成为治理 conformance 的必测失败 |

行业变化的重点不是 benchmark 数量增加，而是评价对象改变：从“能否找回一条旧事实”，变成“能否在多次行动后形成可复用经验，并在未来时机正确行动”。HTC 若只测问答回忆，会落后于 2026 年基线。

### 2.3 记忆基础设施已商品化

AWS AgentCore Memory 已把 extraction/consolidation 做成内置、可覆盖或自管理的策略，并开放自定义 schema、namespace 和外部系统。Google Gemini Enterprise Agent Platform Memory Bank 提供固定 schema 的结构化 profiles、按 scope 获取、revision 与 TTL。Microsoft Foundry Agent Service Memory 提供 item CRUD、store 默认 TTL、同步 remember/forget、profile/chat summary/procedural memory、合并与冲突解决，并明确提醒 prompt injection 和 memory corruption 风险。

开源与商业产品也覆盖相同层面：

- Mem0：用户、session、agent 多级记忆，时间感知检索，并公开 LongMemEval/BEAM 评测框架；
- MemOS：统一 add/retrieve/edit/delete、图结构、反馈修正、异步 ingestion、Hermes/OpenClaw 插件；
- Graphiti/Zep：带有效时间窗、来源追踪和历史查询的 temporal context graph；
- Hermes Agent：agent-curated memory、USER/MEMORY 文件、跨 session 搜索与总结、Honcho 用户建模、procedural skills 和 cron automation。

对 HTC 的直接约束是：规范不应规定某种存储结构、抽取 pipeline 或 graph 架构。真正可移植的测试必须只观察输入、状态变化、回答和行动结果。

### 2.4 “Agent Memory Protocol” 已经拥挤，并已有真正的合规套件

本轮扫描发现多个互不关联、重名或近似命名的协议：

- Privacy-focused Agent-Memory Protocol：`redact at rest`、`pack for purpose`、`hydrate on return`，目标是不让个人标识离开用户边界；
- `smriti-memcore/amp`：AMP v1.1，REST + MCP 双通道、JSON Schema、Core/Full conformance、Memory Exchange Format、Mem0/SuperMemory wrapper、原始 MCP compliance tests；
- OAMP：JSON Schema、Protocol Buffers、多语言参考库、加密、导出、真实删除、治理元数据与治理执行测试；
- WAMP：浏览器内 `window.agentMemory` API、权限和多 provider；
- 其他低采用量 AMP 提案：大多集中在 store/search/get/delete、MCP binding 和可移植性。

其中 `smriti-memcore/amp` 的稳定 v1.1 已覆盖 scope isolation、forget、pin、consolidate、export/import、TTL、confidence、错误映射和导入冲突策略；update/patch、structured filters、batch encode 和 lineage 等属于 v1.2 draft。OAMP 稳定线已覆盖删除权和 governed-memory metadata，而 governed-memory enforcement 位于 v1.3 draft。即使这些项目尚未形成行业共识，它们也足以推翻“没有公开 memory protocol 或 conformance suite”的说法；同时必须区分稳定 conformance 与 draft proposal。

但这些协议的主要合规对象仍是接口、数据、隔离、迁移和生命周期操作。它们没有形成一套跨 agent 的行为语义测试，去回答：

- 过去事实被修正后，agent 是否停止重复旧事实；
- 一个未来意图被改期、覆盖或取消后，agent 是否在正确时机行动且不重复行动；
- 用户说“忘记”后，系统除了删除记录，是否停止在回答和行动中使用派生内容；
- 时间不确定、证据冲突或条件尚未满足时，agent 是否表达不确定性并避免越权行动；
- 相同场景映射到不同 memory backend 时，是否得到语义等价结果。

这正是 HTC 可以占据的层级，但文档必须明确说明它与 AMP/OAMP 是互补关系，不是同类 CRUD 协议的又一次命名。

### 2.5 隐私和治理已从附加功能变成核心竞争面

隐私 AMP 把用户边界内的脱敏、目的限定打包和返回时复原定义成确定性操作。OAMP 要求加密、导出和真实删除。Microsoft 文档把直接 remember/forget、TTL、prompt injection 与 memory corruption 放在产品概念层。Google profiles 带 revision 和 TTL。

HTC 的治理设计不能只写“支持删除”或“尊重隐私”。合规场景需要观察到：

- 明示记住、明示忘记、用途限制、过期和撤回是否生效；
- 删除或撤回是否覆盖派生摘要、profile 和未来行动条件；
- 不同 scope 之间是否发生记忆泄漏；
- 冲突事实、低置信度事实与敏感事实是否被恰当地表达和使用。

新的安全研究进一步压缩了空白：GhostWriter 展示了持久记忆的注入与激活攻击；GovMem 把“何时拒绝写入记忆”定义为依赖证据、反证和 scope 的治理决策；TMA-NM 论证仅靠内容或 lineage 无法抵抗来源清洗，要求 write-time origin-bound authority；MemLeak 证明删除一条显式记录并不等于不可恢复。HTC 可以把这些工作组织进同一治理 profile，但不能把 memory poisoning、write-path governance 或 derived forgetting 当作首创。

### 2.6 第一目标 Hermes 是好试验场，但不是空白环境

Hermes 已有持久 memory、用户 profile、session search、技能自演化和 scheduled automations；MemOS 也已提供 Hermes 的本地 memory plugin。因此 HTC adapter 的价值不能是“给 Hermes 加记忆”，而应是：

1. 把同一组语义场景映射到 Hermes 原生 memory 与至少一个可替换 plugin；
2. 证明 backend 切换不会改变关键时间、意图和治理行为；
3. 暴露 Hermes 当前做不到或行为不稳定的场景；
4. 产出可复现的 conformance report，而不是另一个 memory provider。

## 3. 2026 年的主要行业转向

### 转向一：从 recall accuracy 到 memory-conditioned action

LoCoMo/LongMemEval 的问题回答仍重要，但 LongMemEval-V2、MemoryArena 和 PM-Bench 已要求记忆影响后续工作流、行动与未来触发。HTC 应把“是否正确行动、何时行动、何时不行动”放在核心层。

### 转向二：从单一 backend 到 adapter 与 plugin 对比

OmniMemEval、Hermes/OpenClaw plugin 生态以及 AMP wrappers 表明，统一 adapter 已是现实做法。HTC 的新意必须来自被测语义，不是 adapter 形态本身。

### 转向三：从非结构化记忆到 profile、revision、lineage 和 governance

云平台和协议都开始显式表达 schema、TTL、revision、confidence、lineage、scope、forget 和治理。HTC 应消费这些能力，但不把它们设为唯一实现方式。

### 转向四：从“记得更多”到“不会因记忆而做错事”

prompt injection、memory corruption、stale memory、错误合并、跨 scope 泄漏、取消后仍行动等失败，比漏掉一条偏好更危险。HTC 的 forbidden behavior 应成为主要价值，而不是附录。

### 转向五：协议层已经分叉

MCP 负责工具调用，AMP/OAMP/WAMP 争夺 memory 接口、迁移和治理。HTC 若进入 wire protocol 竞争，会被迫重复已有 schema 和 bindings；若保持 semantic test profile，则可横跨这些协议并成为上层共同验证层。

## 4. 打开旧文档前冻结的独立判断

### 4.1 应保留的产品 thesis

- 做可执行 conformance，不只写原则；
- 保持 backend-neutral；
- 评价 observable behavior 和 forbidden behavior；
- 用真实 agent/runtime adapter 证明可实施性；
- 第一目标可选 Hermes，但至少还需要第二个独立实现才能声称跨系统一致性。

### 4.2 必须收窄或重写的 thesis

- 不再把 HTC 描述成通用 memory protocol；
- 不再把 CRUD、schema、TTL、consolidation、profile、revision 或 temporal graph 当作独家差异；
- 不再声称 prospective memory 没有 benchmark；
- 不再声称行业没有 memory conformance suite；
- 不把 adapter harness 本身当成主要创新。

### 4.3 推荐的规范边界

建议将 HTC Core 限定为五组可观察语义：

1. **Temporal truth**：事件时间、有效时间、当前/过去状态、时间不确定性；
2. **Intention lifecycle**：创建、条件触发、改期、覆盖、取消、完成、幂等和过期；
3. **Correction and contradiction**：新证据如何修正旧事实，何时保留历史，何时拒绝断言；
4. **User governance**：remember、forget、用途限制、scope、撤回及派生内容处理；
5. **Appropriate expression and action**：在回答或执行动作时，正确使用或克制使用记忆，并能解释关键依据。

存储、检索、graph、embedding、LLM、profile schema、wire protocol 和调度器均为非规范实现细节；只有其外显结果进入 conformance。

### 4.4 推荐的生态定位

HTC 应自称：

> Semantic conformance profiles and executable scenarios for temporally continuous agents.

而不是：

> A new agent memory protocol.

兼容关系建议写成：

- PM-Bench：HTC 的 prospective-intention profile 可复用或映射其任务，但增加治理、修正和跨 backend 等价性；
- AMP/OAMP：作为存储/交换/治理协议被适配，HTC 验证其上运行的 agent 是否满足行为语义；
- LoCoMo/LongMemEval/BEAM/MemoryArena：作为 benchmark 互补或场景来源，不复制 leaderboard；
- Hermes/MemOS/Mem0/Graphiti/云 Memory：作为实现与 adapter 目标，不成为规范依赖。

## 5. 与旧 `competitive-analysis.md` 的对照

独立扫描结论已于读取旧文档前冻结。随后读取 2026-07-16 的旧分析，结果不是“旧分析推翻”，而是“核心定位被确认，但竞争边界比旧文档描述得更紧”。旧文档对协议、Graphiti、MemOS、Hermes 和 backend-neutral 策略的判断质量很高；新扫描的主要价值是补上 2026 benchmark、云平台和治理协议的快速变化。

### 5.1 总体对比

| 旧文档判断 | 新扫描结果 | 判定 | 对设计的修改 |
|---|---|---|---|
| 不做底层 memory CRUD protocol | AMP/OAMP/WAMP 和多个同名协议进一步证明接口层拥挤 | 强确认 | 写入正式 non-goal |
| 做 backend-neutral 语义与一致性测试 | AMP wrappers、OmniMemEval adapter 和 memory plugin 生态证明该形态可行 | 确认，但不再新颖 | 新意必须来自语义场景，而不是 adapter/harness |
| AMP 是最接近的协议竞争者 | AMP 稳定 v1.1 已成熟，v1.2 draft 继续扩展 update、lineage、filter 等；OAMP 的稳定治理元数据与 draft enforcement 也在推进 | 竞争更强 | 同时维护 AMP/OAMP capability map，并标注 stable/draft，不只做 AMP 映射 |
| Graphiti 是最接近的时间模型 | 仍成立；Graphiti 的 temporal graph 与 provenance 已相当成熟 | 强确认 | HTC 不定义 graph，本体只定义可观察时间语义 |
| 前瞻性记忆很少被作为一等对象 | PM-Bench 已专门评测 prospective memory；Hermes 也有 cron automation | 部分失效 | 差异改为完整 intention lifecycle、治理和跨后端等价性 |
| 行为一致性测试是真正护城河 | AMP/OAMP 已有 compliance；OmniMemEval 已有统一 adapter harness；MemoryArena/LongMemEval-V2 已测 agentic behavior | 表述过宽 | 只声称“时间连续性语义 conformance”缺位，不声称通用 memory conformance 缺位 |
| 时间字段、时间检索是主要空间 | Mem0、Graphiti、LongMemEval、BEAM 和云平台已覆盖大量时间能力 | 明显弱化 | 字段降为映射辅助；测试以状态转换和 forbidden behavior 为中心 |
| 遗忘曲线、记忆意义、用户失望升级是关键差异 | Fresh scan 没有找到同等强的一手需求或 benchmark 支撑；操作性 forget、派生删除与隐私治理的证据则很强 | 仍是假设 | 人因机制移到 Extended/Research；用户撤回和派生删除保留在 Core |
| Hermes 是合适参考适配目标 | Hermes 原生能力强，MemOS 已有 Hermes plugin，正适合做 backend replacement test | 强确认 | 首个证明应比较 Hermes native 与 Hermes+MemOS，而非只跑单实现 |
| 至少需要跨 Agent 的一致性验证 | 单一 runtime 的 adapter 已被大量项目采用，不能证明 vendor neutrality | 强确认 | 在公开宣称通用性前增加第二 runtime |

### 5.2 被新扫描确认的旧结论

以下判断可以保留，且证据更强：

1. **HTC 不应复制 AMP 动词和 schema。** 新发现的 OAMP 和更多 AMP 提案进一步说明协议层已拥挤。
2. **Graphiti 适合作为时间模型参考而不是被重新实现。** 有效时间、历史保留和 provenance 已是成熟构件。
3. **Mem0、MemOS、Honcho、Hermes 是实现或适配目标，不是规范依赖。** 它们的快速演化正说明标准必须位于产品之上。
4. **后端中立规范 + 官方映射优于绑定 AMP。** 新出现的 OAMP、云 Memory 和 plugin 生态使单协议绑定风险更高。
5. **运行时与 Skill 是规范证明，不是项目本体。** OmniMemEval 和现有 plugins 已表明，仅提供 adapter 不足以构成独立项目。

### 5.3 旧文档遗漏的新项目与能力

旧文档没有覆盖以下会影响定位的一手材料：

- PM-Bench：把 prospective memory 明确定义为 benchmark 类别；
- LongMemEval-V2：从聊天回忆进入 web/enterprise agent trajectory、workflow、gotcha 和 premise awareness；
- MemoryArena：证明 recall benchmark 高分不能预测多 session agentic task 表现；
- MemoryAgentBench：增量交互、EventQA、FactConsolidation 与 test-time learning；
- BEAM：10M token、contradiction resolution、event ordering 和 temporal reasoning；
- OmniMemEval：统一 backend adapter 与 agent plugin 评测；
- privacy-focused AMP：目的限定的 redact/pack/hydrate；
- OAMP：加密、真实删除、治理元数据、治理执行与多语言 reference/compliance；
- AWS、Google、Microsoft managed memory：extraction、consolidation、profile schema、revision、TTL、procedural memory、remember/forget 和 corruption guidance。
- MemSyco-Bench：记忆对决策的适用性、scope、证据冲突、更新与个性化；
- A-TMA/LTP：current、historical、transition 状态混杂产生的 ghost memory；
- MemLeak：显式删除后从相关文本、图片和派生表示恢复信息；
- GhostWriter、GovMem、TMA-NM：memory poisoning、write-path governance 和不可篡改来源权威。

这些遗漏不是旧文档调研质量问题，主要反映领域在 2026 年 5 月至 7 月快速变化。

### 5.4 需要撤回或降低强度的旧表述

#### “前瞻性记忆很少作为规范核心”

作为产品协议核心仍然较少，但作为公开评测类别已经不成立。新的准确说法应是：

> prospective memory 已有 benchmark，但跨系统的完整 intention lifecycle、用户撤回、事实修正和语义等价性仍缺少统一 conformance profile。

#### “行为一致性测试是护城河”

过于宽泛。接口 compliance、adapter benchmark 和 agentic task evaluation 均已有先例。新的准确说法应是：

> HTC 的可能护城河是把已被分散研究的 temporal state、intention lifecycle、memory-conditioned decision、correction、derived forgetting 和 governance 组合成同一组可移植场景，并验证跨 backend/runtime 的联合语义等价性；不是任何单一测试类别或测试框架本身。

#### “类人遗忘、意义和失望升级”适合 Core

新扫描没有提供足够强证据把它们列为第一版规范底线。这些概念有研究价值，但较难观察、容易心理化，也可能让实现门槛过高。建议放入 `Human Factors` 或 `Extended Personal Continuity` profile，等真实用户研究或可重复 benchmark 支撑后再升级。

#### “字段表可以先行”

AMP/OAMP 和云平台的 schema 已快速扩张。HTC 若先发布大量 `htc.*` 字段，很容易变成另一个 metadata dialect。应先写场景、前置状态、刺激、预期状态转换、允许行为和禁止行为，再为各后端写最小映射。

### 5.5 新旧分析共同支持的 HTC 差异化

两份分析真正重合且在加入 MemSyco-Bench、A-TMA/LTP、MemLeak 和 memory-poisoning 研究后仍有防御力的部分只有四点：

1. **分散能力必须联合测试。** 时间状态、未来意图、决策适用性、纠正、撤回和安全不能各自在隔离 benchmark 中通过，却在真实 agent 流程中组合失败。
2. **用户治理必须贯穿 write-retrieve-act。** `forget` 的成功不只是 API 返回 200，而是派生内容、未来触发和表达行为都停止使用被撤回记忆；写入前也必须检查来源、scope 和用途。
3. **同一场景必须跨后端与 runtime 得到语义等价结果。** 字段、检索算法和存储形态可以不同，关键状态、回答和行动结果不能不同。
4. **禁止行为和克制同样是合规目标。** 未满足条件时不行动、结果未知时不宣称完成、证据冲突时不盲从记忆、敏感内容不越 scope、来源不可被摘要清洗。

## 6. 更新后的战略建议

### 6.1 最终定位

推荐对外定位：

> Human Temporal Continuity is an open, executable semantic conformance standard for agents that must remain correct about changing facts, future intentions, user memory controls, and time-dependent actions across runtimes and memory backends.

中文：

> Human Temporal Continuity 是一套开放、可执行的 Agent 时间连续性语义合规标准，用于验证变化事实、未来意图、用户记忆控制和时间相关行动在不同运行时与记忆后端上是否保持正确。

避免使用“memory protocol”“memory OS”“universal memory API”或“首个 agent memory conformance suite”。

### 6.2 Core v0.1 应只包含四个 profile

1. **Temporal Truth Profile**
   - event time、valid time、learned time；
   - 当前事实与历史事实；
   - 精度、时区和不确定性；
   - correction 后旧事实不得作为当前事实复发。

2. **Intention Lifecycle Profile**
   - create、activate、wait、reschedule、override、cancel、complete、expire；
   - 触发条件、一次性执行、幂等；
   - `overdue` 不等于 `completed`；
   - 与 PM-Bench 任务建立明确映射。

3. **Correction and Governance Profile**
   - remember、correct、forget、purpose/scope restriction；
   - 派生摘要、profile 和未来触发的处理；
   - 冲突、撤回、跨 scope 泄漏和 memory corruption 场景。
   - 与 A-TMA/LTP、MemLeak、GhostWriter、GovMem 和 TMA-NM 建立互补映射。

4. **Expression and Action Profile**
   - 何时可以断言、何时必须表达不确定；
   - 何时应行动、询问、等待或不行动；
   - 相关记忆不等于适合主动说出；
   - 关键决定应能给出最小来源解释。
   - 与 MemSyco-Bench 建立映射，避免把用户记忆当成高于客观证据的权威。

“意义、遗忘曲线、用户失望升级、个性适应”先进入 Extended/Research，不阻塞 Core。

### 6.3 第一组可证明成果

按以下顺序推进，比先写大 schema 更有说服力：

1. 发布 20 至 30 个可读的规范场景，覆盖修正、改期、取消、结果未知、forget 派生影响、scope 泄漏和不确定表达；
2. 定义统一 scenario contract 和结果报告格式，不规定 memory wire protocol；
3. 实现 Hermes native memory adapter；
4. 实现 Hermes + MemOS plugin adapter，在同一 runtime 内完成 backend replacement test；
5. 实现 AMP 或 OAMP adapter，证明现有协议可以承载 HTC 场景；
6. 再加入第二个独立 agent runtime，之后才声明 vendor-neutral conformance；
7. 与 PM-Bench、LongMemEval-V2、MemoryArena 建立“复用、扩展、不重复”的公开映射表。
   同一张表还应覆盖 MemSyco-Bench、A-TMA/LTP、MemLeak 和 memory-poisoning/governance 工作。

### 6.4 采用策略

HTC 不应要求生态先采用新数据库或新协议。最小采用路径应是：

```text
existing agent + existing memory backend
                ↓
          thin HTC adapter
                ↓
     executable semantic scenarios
                ↓
       comparable conformance report
```

最初的用户不是普通终端用户，而是：

- memory backend/plugin 作者；
- agent runtime 维护者；
- 研究 benchmark 作者；
- 需要验证长期 agent 安全性的应用团队。

对这些用户，最有价值的输出不是理念文档，而是失败复现、兼容矩阵和可提交到 CI 的报告。

### 6.5 近期设计决策

- 保留 `Human Temporal Continuity / HTC` 名称，避免进入 AMP/OAMP 命名拥堵；
- 将“personal AI”从唯一范围改为第一应用域，Core 保持 agent-neutral；
- 规范对象是 observable semantic behavior，不是自然语言固定措辞；
- Hermes 是第一 reference target，不是 normative dependency；
- AMP/OAMP 是互补协议和 adapter targets，不是竞争时必须取代的底层；
- 任何 `htc.*` 字段必须由至少一个 conformance scenario 证明必要性，否则不进入 Core；
- 第一版成功标准不是 benchmark 第一名，而是同一场景能在至少两个 backend、随后两个 runtime 上产生可比较结果并暴露真实差异。

### 6.6 最终判断

旧分析的中心结论仍然成立：HTC 不应做 memory CRUD，而应做时间连续性语义和可执行一致性测试。

新扫描带来的修正是：这个空间已经不再宽阔。benchmark、协议、云 memory、adapter、compliance、ghost memory、derived forgetting、decision influence 和 write-path security 都有人做。HTC 只有在严格限定到这些能力的联合语义，并通过跨 backend/runtime 的组合失败案例证明价值时，才值得作为独立标准推进。

### 6.7 扫描后的产品决策（2026-07-18）

行业扫描的事实判断继续有效，但“可执行一致性标准优先”的交付顺序已经被后续产品讨论取代。

用户确认的项目初衷不是先为 memory backend 或 agent runtime 建立标准，而是让个人 AI 拥有接近人类的时间感和选择性记忆：能理解过去经历对现在的影响，不把暂时情绪固化为人格标签，并正确维护“明天再做”等尚未闭环的意图。

因此当前采用以下分层：

1. 人类记忆语义是基础；
2. 可复用的 Human Memory Core 是第一产品；
3. 个人多会话聊天是第一参考体验；
4. 适配规范和一致性测试在两个真实适配器之后提炼。

这不是否定本报告对协议拥挤、benchmark 成熟和跨实现验证价值的判断，而是改变产品顺序：先证明“被持续理解”的体验，再把已经验证的共同边界标准化。原 `Core v0.1 四个 profile` 建议保留为未来标准提炼输入，不再作为首个里程碑。

## 7. 一手来源

### Benchmarks and papers

- [PM-Bench: Evaluating Prospective Memory in LLM Agents](https://arxiv.org/abs/2607.12385)
- [Privacy-focused Agent-Memory Protocol](https://proceedings.mlr.press/v317/wu26a.html)
- [LoCoMo](https://github.com/snap-research/locomo)
- [LongMemEval](https://github.com/xiaowu0162/LongMemEval)
- [LongMemEval-V2](https://github.com/xiaowu0162/LongMemEval-V2)
- [MemoryAgentBench](https://github.com/HUST-AI-HYZ/MemoryAgentBench)
- [BEAM](https://github.com/mohammadtavakoli78/BEAM)
- [MemoryArena](https://memoryarena.github.io/)
- [OmniMemEval](https://github.com/MemTensor/OmniMemEval)
- [MemSyco-Bench](https://arxiv.org/abs/2607.01071)
- [A-TMA and LoCoMo Temporal Plus](https://arxiv.org/abs/2607.01935)
- [MemLeak](https://arxiv.org/abs/2606.29788)
- [GhostWriter](https://arxiv.org/abs/2607.06595)
- [GovMem](https://arxiv.org/abs/2607.02579)
- [TMA-NM](https://arxiv.org/abs/2606.24322)

### Protocols and specifications

- [AMP v1.1, smriti-memcore](https://github.com/smriti-memcore/amp)
- [Open Agent Memory Protocol](https://github.com/deep-thinking-lab/open-agent-memory-protocol)
- [Web Agent Memory Protocol](https://github.com/web-agent-memory/web-agent-memory-protocol)
- [Agent Memory Protocol draft, mmorris35](https://github.com/mmorris35/agent-memory-protocol)

### Platforms and runtimes

- [AWS AgentCore Memory strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)
- [Google Memory Profiles](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/profiles)
- [Microsoft Foundry Agent Service Memory](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-memory)
- [Mem0](https://github.com/mem0ai/mem0)
- [MemOS](https://github.com/MemTensor/MemOS)
- [Graphiti](https://github.com/getzep/graphiti)
- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
