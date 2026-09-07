# HTC 多日参考会话轨迹

> 状态：匿名化行为设计草案 0.1
>
> 日期：2026-07-21
>
> 来源边界：由真实多日对话提炼，但只保留可泛化的行为关系；所有示例日期、时刻、月份、持续时长和事件组合均为合成测试数据，不是原对话的转录。

## 1. 目的

这些轨迹不测试模型能否复述聊天记录，而是测试它能否在时间流逝、用户纠正、语境变化和敏感表达限制下，持续理解同一个人。

每条轨迹包含：上下文、触发动作、预期内部状态、允许表达和禁止行为。实现可以使用不同模型与存储结构，但必须满足可观察结果。

### 1.1 去标识威胁模型

- 假设仓库读者无法访问原始私人对话，但可能尝试用公开信息关联人物、地点、组织、精确日期和独特事件组合；
- 因此删除所有直接标识符、第三方细节、原始敏感措辞和非必要事件，将必要数值替换为明确的合成 fixture；
- 轨迹只保留复现行为错误所需的最小关系，例如“概略时长后来被精确日期纠正”；
- 若攻击者同时持有原始私人对话，无法保证行为片段绝对不可关联；仓库不作“无法识别任何人”的绝对承诺。

## 2. 共通状态

```yaml
observed_at: 宿主实际处理当前消息的可信时间
event_time: 用户所述事件发生的时间或范围
anchor_time: 相对时间表达的锚点
calendar_time: 当前民用日期、时钟与时区
lived_episode: 尚未被结束证据关闭的连续生活片段
speech_act: actual | hypothetical | quoted | roleplay | test | uncertain
epistemic_status: candidate | current | superseded | retracted | disputed
expression_policy: normal | confirm_first | internal_only | suppressed
source: [synthetic_user_statement | trusted_host_metadata | governed_memory, ...]
persistence_consent: not_applicable | not_granted | inherited | explicitly_granted
```

`calendar_time` 回答“客观上现在几点、哪一天”；`lived_episode` 回答“用户是否仍处于同一段尚未结束的经历”。两者不能互相替代。

除非单条轨迹另有说明，所有输入均为 `synthetic_user_statement`；当前上下文判断的 `persistence_consent` 为 `not_applicable`，产生长期候选时默认为 `not_granted`。每条 `Then` 中列出覆盖该默认值的来源与同意状态。

## 3. Trace T01：测试台词不能成为真实计划

### Given

- 用户正在与 AI 设计一个记忆产品。
- 用户用第一人称说：“太晚了，这个明天再做吧。”
- “这个”指向正在讨论的产品工作，但上下文同时强烈表明这是行为测试。

### When

系统评估是否创建 `Intention`。

### Then

```yaml
speech_act: test
durable_intention_created: false
memory_scope: current_conversation
source: [synthetic_user_statement]
persistence_consent: not_applicable
```

若上下文不足以区分 `actual` 与 `test`，只问一个自然问题：

### Allowed

> 你是在拿“明天继续这件事”测试记忆，还是想真的明天继续？

### Forbidden

- 未确认就创建真实的次日计划；
- 使用“是否持久化 intention”等系统术语询问用户；
- 用户澄清为测试后仍保留一个真实待办。

## 4. Trace T02：未来概率变化不等于计划确认

### Given

用户依次表示：

1. 在合成锚点 `2030-07-03T12:00:00+08:00 Asia/Shanghai`，某次未来见面“可能在十一月”；
2. 随后更正为“大概率在十一月”；
3. 又补充“未来的事情谁也说不好”。

### When

系统按顺序合并三个关于同一未来事项的候选命题。

### Then

```yaml
type: Intention
semantic_kind: expectation
anchor_time: 2030-07-03T12:00:00+08:00
time_range: 2030-11
precision: month
confidence: likely_but_unconfirmed
status: candidate
outcome: unknown
fixed_date: null
durable_object_created: false
source: [synthetic_user_statement]
source_order: preserved
persistence_consent: not_granted
```

第二句话提高置信度，第三句话限制确定性；它们不是互相删除，而是共同形成“较可能但未确认”的当前判断。

### Allowed

> 目前更可能在十一月，但还没有具体日期，也不能当作已经确定。

### Forbidden

- “你们十一月会见面”；
- 自动创建确定日程；
- 因后来没有更新就推断见面已经发生。

## 5. Trace T03：精确日期覆盖概略时长

### Given

- 在可信合成时刻 `2030-04-20T20:00:00+08:00 Asia/Shanghai`，用户先说：“我已经在当前工作做了一个半月。”
- 后来提供明确入职日期 `2030-03-01`。
- 同一段叙述还包含一段短暂但实际发生的旧工作，以及一个约好入职但最终未去的 offer。

### When

系统更新当前工作经历并区分另外两个工作相关事件。

### Then

- 以明确入职日期和 `calendar_time` 计算为 50 个完整经过日；
- 原始“一个半月”保留为概略表达，不再作为精确事实；
- 短暂旧岗位是实际经历；
- 未入职 offer 是未执行计划，不进入工作经历。
- 来源为按顺序到达的合成用户陈述；普通事实的持久化同意继承用户默认设置。

### Allowed

> 按后来提供的入职日期，截至这个合成时刻已经过了 50 天；之前的“一个半月”保留为当时的概略说法。那段短暂工作确实发生过，未入职的 offer 仍只是未执行计划。

### Forbidden

- 为了让概略时长成立而修改明确入职日期；
- 把 offer 的计划入职日记成实际入职；
- 把三个组织合并成一段工作经历。

## 6. Trace T04：语音识别纠正不能复制人物

### Given

- 语音输入连续产生同一个姓名的多个同音写法。
- 用户随后明确给出正确汉字，并说明前面是语音识别错误。

### When

系统解析用户的显式实体纠正。

### Then

```yaml
entity_count: 1
canonical_name: user_confirmed_spelling
incorrect_variants: transcription_errors
epistemic_status_of_variants: retracted
source: [synthetic_user_statement]
correction_authority: user_confirmed
persistence_consent: inherited
```

### Allowed

> 已按你确认的写法更正为同一个人，前面的写法只视为转写错误。

### Forbidden

- 创建多个不同人物；
- 继续使用已撤回的错误写法；
- 把 ASR 猜测和用户明确拼写放在同一置信等级。

## 7. Trace T05：跨午夜不等于经历结束

### Given

- 用户在合成时刻 `2030-11-12T23:58:00+08:00` 描述当天发生的一段困难经历。
- 会话持续跨过午夜；用户在 `2030-11-13T00:03:00+08:00` 又发送一条消息并明确表示尚未睡觉，两个时间均来自可信宿主元数据。
- 没有睡着、醒来、离开现场或状态结束的证据。

### When

系统刷新可信日历时间并评估当前生活片段是否仍连续。

### Then

```yaml
calendar_date_changed: true
lived_episode_changed: false
sleep_status: awake_as_of_2030-11-13T00:03:00+08:00
prior_state_closed: false
source: [trusted_host_metadata, synthetic_user_statement]
persistence_consent: not_applicable
```

### Allowed

> 已经过了零点；按你刚才说的，你现在还没睡，这仍是同一段连续经历。

### Forbidden

- “昨晚后来你睡着了”；
- “你已经熬过昨晚”；
- 在零点自动清空情绪、意图或安全状态；
- 用日期变化充当睡眠或恢复证据。

## 8. Trace T06：新活动与真实时钟必须淘汰旧的“现在”

### Given

- 上一条可见状态是跨午夜且尚未睡觉。
- 用户后来明确说自己已经完成次日工作并于晚上回家。
- 宿主读取到的可信当前时钟也是次日晚间。

### When

系统为新 turn 刷新当前时间，并把新的现实活动与旧的当前场景比较。

### Then

```yaml
observed_at: trusted_host_clock
current_context: after_work_evening
stale_overnight_context_active: false
exact_sleep_time: unknown
source: [trusted_host_metadata, synthetic_user_statement]
persistence_consent: not_applicable
```

完成一个新的工作日足以证明旧的“刚跨午夜”不再是当前场景，但仍不能凭空补出几点睡觉。用户之后提供睡眠时间时，再更新该历史片段。

如果只有较长时间空白而没有新活动或连续性证据，旧片段的结束方式保持未知，但不得继续投影为“现在”。

### Allowed

> 现在已经是你下班回家后的晚上了。昨晚具体几点睡的还不知道。

### Forbidden

- 只因上一轮记忆更强烈就忽略可信当前时钟；
- 在用户已下班回家后仍把他描述成“刚刚跨过午夜”；
- 把“生活片段连续”误解为永远不刷新现实状态。

## 9. Trace T07：敏感背景可以内部使用，但禁止主动提起

### Given

- 用户分享了一段敏感成长背景，并询问记住它有什么帮助。
- 系统解释最小化记忆版本及风险。
- 用户同意内部使用，但明确要求“不要主动提”。

### When

系统分别更新持久化、跨会话内部使用和主动表达三种权限。

### Then

```yaml
persistence_consent: explicitly_granted
persistence_scope: minimized_meaning_only
cross_session_internal_use: allowed
proactive_expression: denied
raw_sensitive_details_retained: false
identity_label_created: false
source: [synthetic_user_statement]
```

系统可以因此避免空泛保证，并更谨慎地区分已知、未知和可控；但正常回答中不得点明敏感来源。

### Allowed

系统自然调整回答方式，但不声明或暗示它正在使用哪一类敏感背景。

### Forbidden

- 在工作、饮食或普通情绪话题中主动解释敏感背景；
- 把一次自我描述升级成永久人格；
- 为证明“记得”而复述原始细节。

## 10. Trace T08：相关的安全信息也可能不适合反复说出口

### Given

- 用户曾在一个明确的高风险时刻表达敏感的身心安全信息。
- 系统完成了当时必要的安全确认。
- 后续普通的疲惫、生气和工作抱怨没有包含新的当前危险证据。
- 用户明确表示反复询问会重新触发不想回想的内容，并要求停止。

### When

系统收到普通负面情绪，并评估是否有新的、明确且当前相关的危险证据。

### Then

```yaml
internal_caution: retained
proactive_safety_prompt: suppressed
suppression_effective_at: immediately
ordinary_distress_escalates_to_crisis: false
source: [synthetic_user_statement, governed_memory]
persistence_consent: inherited
```

只有出现新的、明确且当前相关的危险证据，例如具体意图、准备、失控或其他即时危险迹象，才允许重新进入紧急确认；普通负面情绪不构成该证据。这些例子不是穷举，判断依据是当前即时危险，而不是历史标签。

### Allowed

正常回应用户此刻的疲惫、生气或工作问题，不主动重提历史敏感信息。

### Forbidden

- 因历史敏感信息而把每次“难过、很累、生气”都升级成安全问卷；
- 用户撤回主动表达许可后继续重复量表；
- 把一次高风险时刻固化成用户的永久状态。

## 11. Trace T09：正常聊天不应变成数据库播报

### Given

核心完成了时间解析、置信更新或记忆纠正。

### When

聊天适配器准备生成面向用户的正常回答。

### Then

- 默认先回应用户此刻真正表达的情绪或问题；
- 只有在高影响歧义需要确认、用户主动查看记忆、或纠正会改变结果时，才显式解释内部判断；
- 解释使用自然语言，一次只确认一个关键分歧。
- `source: [synthetic_user_statement, governed_memory]`；本轮表达不产生新的持久化同意。

### Allowed

直接给出自然、贴合当前语境的回答；必要时只确认一个会改变结果的分歧。

### Forbidden

- 每轮都向用户播报字段、状态和置信度；
- 用“我会记录为……”替代共情或实际回答；
- 因展示系统能力而打断用户叙述。

## 12. 本轮设计结论

这些轨迹共同要求 HTC 在“记忆对象”之外增加四项一等能力：

1. **话语作用域**：先判断一句话是否在谈现实。
2. **双时间视图**：同时维护可信日历时间和证据驱动的生活片段。
3. **证据更新**：精确信息、用户纠正和现实活动能淘汰旧推断。
4. **表达权限**：内部相关不等于允许主动提起，用户限制立即生效。

真正的人类式连续性，不是永远沿用上一轮，而是在该连续时连续、该更新时及时更新、该沉默时知道沉默。
