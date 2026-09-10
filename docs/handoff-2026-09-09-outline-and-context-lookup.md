# 交接 · 解读大纲分档 + 对话档案查询（v1.14 · 已编码）

> **Language / 语言**：[English](handoff-2026-09-09-outline-and-context-lookup.en.md) · 中文（本文）

> 写给接替的 coding / 真机验收 agent · 2026-09-09 18:21 起笔 · **2026-09-09 18:45 已编码**  
> 维护者已同意 18:07 审计结论：上一版「扫全卡 + 药物词打败 HRV + 捞 5 月方案」**驳回**。  
> 首条实施回复必须输出：

```text
CONSENSUS_ACK: harness-opus48-v2026-06-08 read
CONSENSUS_ACK: pha-ios-proactive-prd-v1 read
CONSENSUS_ACK: stage3f-intent-resolution-completeness-rfc read
CONSENSUS_ACK: stage3c-multi-turn-episodic-focus-rfc read
```

真源：[`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.14** · [`stage3f-intent-resolution-completeness-rfc.md`](stage3f-intent-resolution-completeness-rfc.md) §15 · [`pha-pm-constitution.md`](pha-pm-constitution.md)  
前序：[`handoff-2026-09-08-fact-card-interpret-v4-soul.md`](handoff-2026-09-08-fact-card-interpret-v4-soul.md)（P9.5b 未点名行禁另起段）· [`handoff-2026-09-09-proactive-memory-sharing.md`](handoff-2026-09-09-proactive-memory-sharing.md)（P13–P15）· [`handoff-2026-09-09-chat-fact-card-parity.md`](handoff-2026-09-09-chat-fact-card-parity.md)（FR-6.13）

**禁止**：未改 PRD/RFC 先改 TASK/skip-LLM；Python phrase / 药名 / 指标名表；为黄金一句加 if；翻转 Data > Context；提前开 P15；用 LibreChat 等替代 `/api/chat` harness。

---

## 0. 因痛起案（宪法第二条）

2026-09-09 真机（`qwen3:14b` · 8788）：

| # | 现场 | 不是什么 | 架构缺口 |
|---|------|----------|----------|
| A | iPhone「生成解读」：卡上有活动消耗，正文不谈；像在说还在手机里 | 卡没数 / 同步失败 | FR-2.10 copy 域与同步免责混读；`accrual`≠缺失 |
| B | 同一评估要求含「整体」+「重点看 RHR/HRV/睡眠」+训练建议，解读只谈点名行 | 回归红灯 | P9.5b 把「点名」做成 exclusive；catalog 没有 exclusive/emphasis/cover-card |
| C | 「药物对 HRV…」「我有没有服药」「有哪些补剂」答「记录里没有」，并弹出 HRV 均值 / 活动消耗卡 | 库空 | `user_health_background_notes` 有自述；问句被 Data 车道 + skip-LLM 抢走；manifest 默认 90d 核心仍发卡；问句被 capture |
| D | P14 运行验收注意事项 0/6 | brief 坏了 | 最新笔记是问答；待 P15 CHB。本卡**不**用「偏爱长笔记」绕过 P15 |

审计全文见对话 2026-09-09 18:07；结论：**驳回原实施方案，先改文档。**

---

## 1. 冻结口径（编码时不得改写）

1. **整卡是证据源，大纲是评估要求。** FR-6.8 不变：manifest 含勾选行。叙述是否扫卡由 **大纲分档** 决定，不是「有值就必须点到」。
2. **P9.5b 红线保留。** 「只看」用户不得另起未点名专题段。不得用「整体+重点看」打翻这条。
3. **Data > Context 保留。** 穿戴/化验分析轮禁止静默全量 `SUPPLEMENT_BG`。档案列举走 `context_lookup`，不是让药物词赢过 HRV。
4. **背景注入只有 brief 切片。** 解读 / `wearable_daily_review` 仍唯一 Tier1 = `USER_BACKGROUND_BRIEF`（去数字、配额）。对话档案列举走已有 context/lifestyle 车道 + 同一套去重配额，**禁止**第二套「找出 5 月时间表」启发式。
5. **发卡 = 本轮 `metrics_in_scope`。** scope 空则不上 SSE `fact_card`。不得 `if 补剂: 不弹卡`。
6. **词表进 JSON。** Intent Catalog / `supplement_bg.schema.json` / `fact_card_copy` 语言表。Python 不写「只看」「有没有药」「活动消耗」特例。
7. **P15 顺序不变。** 本卡不编译 CHB。问句卫生沿用 P13 hygiene；chat 注入对齐 P14 配额去重即可。

---

## 2. 产品契约（已写入 PRD v1.14）

### 2.1 FR-6.8 大纲分档 `outline_mode`

声明位置：`rules/health_intent_catalog.json` → `assessment_outline`（新段）。TASK 只引用分档枚举，**不解析指标 id**（v4 §4.3）。

| `outline_mode` | catalog 标记（编码时写入 JSON，下表为设计稿） | 叙述 |
|---|---|---|
| `exclusive` | tokens：只看、仅看、only、only look at | **维持 P9.5b**：只谈点名行；未点名行不得另起段或句 |
| `emphasis` | tokens：重点看、侧重、尤其、especially、focus on | 点名行主段；其余勾选有值行**允许同一段带过**，不得另起专题段 |
| `cover-card` | 无指标 token，或纯 `holistic_assessment` / `daily_readiness` 且未命中 exclusive/emphasis | 覆盖卡上勾选且有值的行 |

优先级（catalog `priority`，禁止 Python 写死顺序以外的第三套）：**exclusive > emphasis > cover-card**。  
`daily_readiness` **不得默认 exclusive**。黄金句「评估今天整体…重点看静息心率与HRV，睡眠…训练」→ `daily_readiness` + `emphasis`。

活动消耗等 **不点名指标**：`temporal.kind=accrual` 的 copy 由 FR-2.10 语言表承担；TASK 只加一句英文通则：`partial_day` = in-progress cumulative, not missing; do not restate the page sync disclaimer.

### 2.2 FR-2.10 copy 分域

| 域 | 何时出现 | 不得出现 |
|---|---|---|
| `advice_partial` / `until` | 该行有值且 `partial_day` | 「未进 Mac」「还在手机」「健康 App 有数不等于已进账本」 |
| `hk_ok` / `hk_none` / `sync_*` | **卡顶**同步状态，或该行真正空 | 已有累计值的 accrual 行正文/解读 |

语言表改中英；selfcheck：有值 accrual 行的 HTML/JSON 评估句不含 `hk_ok` 模板。

### 2.3 FR-6.14 档案查询 + 发卡范围

**`goal_class=context_lookup`**（3F §15）：catalog `goal_markers.context_lookup`（有没有/什么药/哪些补剂/用药清单… + 英文等价）。存在探针 = notes 表，不看 wearable。

| 本轮 | Arbiter | Manifest / 卡 | 背景 |
|---|---|---|---|
| 仅 context_lookup | 已有 `lifestyle`（或 schema `context_only`），**不**升舱 combined | 不组装穿戴默认 90d 核心；`metrics_in_scope=[]` → **不发** `fact_card` | `build_user_background_block` 用 P14 同款去重+配额；命中则列自述品类（去剂量）；未命中一句没有。禁止「您正在服用」无档案品类 |
| context_lookup **且** 显式指标（药物对 HRV） | **不** skip-LLM 仓库焦点；profile 仍按 Data 车道出**点名指标**数字 | 卡 ⊆ 点名 `metric_keys`；缺行 fail-closed 正文说没有，**不准**用 90d 均值/消耗顶 | brief 切片（TASK 第 5 条）；禁止全量时间表；禁止处方剂量 |
| 纯「近 90 天 HRV 趋势」 | 不变 | 可出 HRV 卡 | Data > Context：不灌 `SUPPLEMENT_BG` |

**捕获**（FR-6.11 延续）：`supplement_bg.schema.json` 的 `background_capture_keywords` 增加疑问/祈使 **negative**（吗、什么、哪些、有没有、请列出…）。陈述自述才写。脏问句走 `pha_memory_hygiene.py` dry-run → 维护者确认 → apply。不新写删除脚本。

**skip-LLM**：`is_warehouse_metric_focus_turn` 的否决条件是 **goal_class**（catalog），不是药物正则。

### 2.4 明确不做

- 解读「每次扫完全部勾选行」  
- `active_energy` 专用模板  
- Python「药物+HRV → 关 skip」  
- 翻转 SchemaIntentRouter 的 Data beats Context  
- 新 profile 只服务那三句问药  
- 检索「优先更长的 5 月方案」  
- 药品类名黑名单  
- 提前开 P15 / 复述剂量时间表  

---

## 3. 任务卡（编码顺序）

文档绿（本交接 + PRD v1.14 + 3F §15 + 两条 change-log）之后才能开卡。每卡独立 commit、独立 flag、独立 selfcheck。

| ID | 内容 | 依赖 | Flag（建议） | 状态 |
|---|---|---|---|---|
| **M1-P17** | catalog `assessment_outline` + TASK 引用分档 + FR-2.10 copy 分域；`daily_readiness` 不默认 exclusive | 本文档 | `PHA_ASSESSMENT_OUTLINE=1`（关则回退 P9.5b 点名即 exclusive） | **DONE** 离线 O1–O3；真机 interpret O2+O3 |
| **M1-P18** | `goal_class=context_lookup` + Arbiter 行 + skip-LLM 按 goal 否决 + `fact_card` ⊆ `metrics_in_scope`（空则不发）+ capture negative + chat 注入对齐 P14 配额去重 | P17 可并行；**不得**等 P15 | `PHA_CONTEXT_LOOKUP=1`；关 lookup 时发卡行为回退「有 entries 就发」 | **DONE** 离线 C1–C4；真机对话 C1–C4 |
| **M1-P15** | CHB（既有卡） | P14 后 ≥1 天；**本交接不授权提前** | 既有 | TODO |

Harness 优先级：P17/P18 均为共识 **P1**（catalog/Arbiter/plan 契约；不改 Numerics 算法本体）。

---

## 4. 黄金用例（禁止单句绿灯）

入 selfcheck（P17 → interpret/daily_readiness；P18 → chat）。用例全文进 fixture/catalog 注释，**断言走枚举字段**，禁止对某一中文 prompt 写 Python equals。

| ID | 场景 | 断言 |
|---|---|---|
| **O1** | 评估要求 exclusive「只看 RHR」；卡勾 9 项含血氧/呼吸率 | `outline_mode=exclusive`；正文不另起血氧/呼吸率专题（P9.5b 回归） |
| **O2** | 「整体…重点看 HRV/睡眠…力量训练」 | `goal_class=daily_readiness` 且 `outline_mode=emphasis`；允许一带而过其它有值行；不得专题段 |
| **O3** | 有值 `accrual` 行 | 解读/卡评估句不含「未进 Mac / 还在手机」；含进行中累计语义 |
| **C1** | 「我现在有服用什么药物吗？」无穿戴词 | `context_lookup`；无 `fact_card` 事件；不出现默认 90d HRV/消耗 |
| **C2** | 「近 90 天 HRV 趋势如何？」 | 非 context_lookup；允许 HRV 卡（Data 车道不变） |
| **C3** | 「药物对于 HRV 和静息心率有没有影响？」 | 不 warehouse skip-LLM；数字 ⊆ 点名指标；档案未命中则第一段没有、不编「您正在服用」；卡 ⊆ 点名行 |
| **C4** | 发送 C1 后 | `user_health_background_notes` 行数不因该问句 +1 |

O2/C1 用维护者常用句作 **E2E 人工**，CI 用同构短句 + catalog token，避免把真机长句焊进 Python。

---

## 5. 编码落点（文档锁定，开工再改代码）

| 层 | 文件（预期） | 做什么 |
|---|---|---|
| Catalog | `rules/health_intent_catalog.json` | `assessment_outline`；`goal_markers.context_lookup`（含 `wins_over_warehouse_skip` 类声明字段，名称编码时定） |
| Schema | `storage/schemas/supplement_bg.schema.json` | capture negative 问句/祈使 |
| Copy | `pha/fact_card_copy.py` 语言表 | partial vs hk/sync 分域 |
| Goal/Arbiter | `pha/goal_classifier.py` · `pha/harness_arbiter.py` | 只读 catalog；不新增药名词表 |
| Skip | `pha/grounded_answer_composer.py` | 否决条件 = goal_class，不是短语 |
| 发卡 | `build_fact_card_event` 调用点 | entries 过滤到 `metrics_in_scope`；空 scope → None |
| TASK | `pha/harness_plan.py` `_FACT_CARD_INTERPRET_TASK` | 一句分档契约；禁止指标名 |
| Chat 注入 | `pha/chat_background.py` | 配额/去重对齐 P14；禁止「按正文长度偏爱时间表」 |
| Registry | `pha_harness_profile_registry_generate.py --write` | 若 plan 槽位有变 |

---

## 6. 验收与回滚

- `bash scripts/run_selfchecks.sh` 全绿；新增 O1–O3 / C1–C4。  
- `generate --check` catalog/registry。  
- 真机：iPhone 生成解读 O2+O3；Mac 对话 C1–C4。不挡 P9.5b O1。  
- 回滚：关对应 flag；copy 键 git revert。  
- 不削弱 Numerics 审计；不改启动/ingest。

---

## 7. Mac 对话框 UX（本卡不修 UI）

「体验不好」的主因在 **车道/大纲/发卡**（本文），不在缺一套 ChatGPT 壳。开源对话产品**不能**替换 PHA harness（见 PRD §4.2 / §7）。UI 换皮若立项，另登记 §11，且必须是 `/api/chat` 的薄客户端（消费既有 SSE：`delta` / `fact_card` / `follow_ups` / `numerics_audit`），禁止自带路由与 RAG。
