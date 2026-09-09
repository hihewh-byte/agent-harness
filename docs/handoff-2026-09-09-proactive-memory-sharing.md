# 交接 · 主动 Agent 与 PHA 记忆共享：先止漏，再分层共享（M1-P13 / P14 / P15）

> 写给接替的 coding agent · 2026-09-09 12:10 起笔 · 依据本机 `data/pha_storage.db` 查库证据（§1）与维护者 12:00 拍板（§2）  
> 首条回复必须同时输出两行：  
> `CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`  
> `CONSENSUS_ACK: harness-opus48-v2026-06-08 read`  
> 真源：[`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) v1.12（§1.3a 第二含义 / FR-6.11–6.12 / §8 P13–P15）· [`pha-pm-constitution.md`](pha-pm-constitution.md)（反硬编码、禁止对特定用例打补丁）· 上一份交接 [`handoff-2026-09-08-fact-card-interpret-v4-soul.md`](handoff-2026-09-08-fact-card-interpret-v4-soul.md)（§4.3「大纲在 TASK、不解析指标 id」仍有效）  
> 本文**只含设计，不含代码**。三张任务卡**严格按 P13 → P14 → P15 顺序**，每张卡独立 commit、独立验收；上一张未绿不得开下一张。

---

## 0. 现场状态与开工顺序

**git**：`main` 本地领先 `origin/main`（含 `0ed4898`：`OLLAMA_THINK` env 开关），维护者手动 push。工作区应干净；不干净先问维护者。

**运行时**：PHA `:8788`（launchd `com.personal-health-agent.pha-8788`），build `pha-v2.3.34-fact-card-task-p95b`；模型已切 **`qwen3:14b`**（`OLLAMA_MODEL` / `OLLAMA_MEDICAL_MODEL`），`OLLAMA_THINK=false`；env 在 `~/Library/Application Support/pha/env-8788.sh`（ingest token 也在里面，**不得**回显到对话或日志）；重启用 `bash scripts/pha_restart_accept.sh`。`OLLAMA_KEEP_ALIVE=0` 未动（每次解读冷加载 9.3 GB，约 70 s；是否改 `10m` 由维护者定，不在本文范围）。

**测试基线**：`.venv/bin/python -m pytest -q tests/` 当前 61 通过 + 1 **既有**失败 `test_selfcheck_manifest[wearable_golden_fixture]`（`hrv_rmssd_ms` 黄金夹具缺可比行，与本文无关，不要顺手修）。

**用户 prefs**：`data/fact_card_prefs.json` zh-CN，评估要求原文：`重点看静息心率与HRV，睡眠的各项指标，用一两段话说清楚这样的数值对于今天的运动训练有哪些建议，比如运动类型运动强度的建议，是否可以进行力量训练？`。测试改过之后**必须原样恢复**。

开工顺序：

1. 读 §1，按 §1.3 的 SQL 自己在本机复现一遍数字（数字会随使用增长，量级对即可）。
2. P13（§4）：止漏 + 清理。selfcheck 绿、清理 dry-run 经维护者确认后 apply。
3. P14（§5）：背景 brief 进解读。selfcheck 绿 + §5.8 运行验收 6/6。
4. P15（§6）：CHB 统一供给。P14 验收后 ≥1 天再开。

---

## 1. 问题与证据

### 1.1 结论先行

PRD §1.3a「不割裂」目前只落在**数字账本**（事实卡规则层用全量 SQLite 历史做递进基线）。用户几个月对话沉淀下来的**非数字记忆**（补剂/用药/生活习惯自述、长期画像）对按钮式解读 `fact_card_interpret` **完全不可见**——这是 FR-6.8 的刻意设计（证据面收窄、fail-closed），不是漏接。

但反方向**在漏**：解读轮借用 chat 管线时，把合成消息和解读正文**写进了用户的聊天记忆**。所以现状不是「隔离」，是「chat → proactive 被挡死，proactive → chat 无审计写入」。

### 1.2 查库证据（2026-09-09 11:57，`data/pha_storage.db`）

| 表 | 总量 | 其中由解读轮产生 | 说明 |
|---|---|---|---|
| `chat_sessions` | 1152 | **56**（另有 6 个空会话） | 每按一次「生成解读」新建一个会话 |
| `chat_messages` | 13524 | 56 条 user + 对应 assistant | user 内容 = `Generate today's fact-card interpretation`（现）或 `请根据系统提供的当日事实卡数字与基线摘要…`（旧） |
| `user_health_background_notes` | 158 | **7** 条 category=`medication` | 旧版中文合成 prompt 含「处方/用药剂量」，被 `should_capture_background` 捕获 |
| `user_health_background_notes` | — | **17** 条 category=`unstructured_vision` | 内容为 `[vision_parse_failed] Server error '500 …'`，是错误串不是记忆（附带发现，见 §4.4） |
| `chat_session_turn_focus` | 1008 | 7 | 解读会话的 turn focus |
| `chat_session_active_recall` | 807 | 0 | 未受影响 |
| `chb_briefs` | **0** | — | CHB 从未编译过（P15 的起点） |

真实用户记忆规模：`supplement` 124 条、`medication` 12 条（含 7 条污染）、`sleep_lifestyle` 4 条、`symptom` 0、`general` 1。

### 1.3 复现 SQL（只读，不进仓库）

```sql
-- 解读轮制造的会话
select count(distinct session_id) from chat_messages
 where role='user' and (content like 'Generate today''s fact-card interpretation%'
                     or content like '请根据系统提供的当日事实卡%');
-- 污染的背景笔记
select category, count(*) from user_health_background_notes
 where content like '请根据系统提供的当日事实卡%' or content like '[vision_parse_failed]%'
 group by 1;
```

### 1.4 代码根因

- `pha/fact_card_interpret.py` `run_interpretation` 以 `session_id=None` 调 `stream_pha_chat_events`。
- `pha/chat_turn_orchestrator.py` `orchestrate_chat_turn_events`：`sid` 为空 → `create_session(uid)`（约 213–220 行）；随后 `append_message(sid,"user",…)`、`maybe_set_title_from_first_message`、`dynamic_slot_registry.on_request_start`、`maybe_capture_chat_background`（约 237–264 行）；收尾 `append_message(sid,"assistant",…)` + `record_health_turn_focus`（约 924–943 行）；中段 `session_turn_focus.save/consume`（约 493–564 行）。这些写入对 profile 一视同仁，没有「本轮是否属于用户聊天记忆」的概念。
- 读侧已隔离：`pha/chat_turn_slots.py` 对 `fact_card_interpret` 置 `background_block=""`、`recalled_snippets=""`；`pha/harness_plan.py` `_FACT_CARD_INTERPRET_FORBIDDEN` 禁 `SUPPLEMENT_BG` / `WEARABLE_90D_SUMMARY` / `PATIENT_STATE_*` / dossier / 工具。`EPISODIC_BRIDGE` 在 `episodic_all_profiles_enabled()` 时对非附件 profile 都会拼（`chat_turn_slots.py` 约 391–399 行），但解读轮无 session focus，实际为空——P13 要把它变成显式规则而不是靠「恰好为空」。

---

## 2. 维护者拍板（2026-09-09 12:00）

> 「同意你的建议……主动 agent 也是 PHA 的一部分，评估就是对用户整个历史背景下的增量数据的评估。」

采纳的分层方案（**冻结**）：

| 层 | 内容 | 对按钮解读 | 方向 |
|---|---|---|---|
| **A 结构化事实层** | 数字账本（已共享）+ `user_health_background_notes` 里的补剂/用药/生活习惯**自述** | **共享**，作为**非数字源**的 Tier1 brief | chat → proactive（P14）；proactive 产出**不再**写 chat 表（P13） |
| **B 情景/会话记忆** | `chat_session_turn_focus`、RECALL 片段、`EPISODIC_BRIDGE`、上轮摘要 | **不共享**（无对话上下文的一次性解读用不上，只会带主题漂移） | 维持 `recalled_snippets=""`，并显式禁 `EPISODIC_BRIDGE` |
| **C 跨 session 长期画像** | CHB（`chb_compiler`，`USER_CONTEXT_BRIEF` 槽） | **共享**，但要先让 CHB 真的编译起来，并把 A 层与解读历史纳入编译输入 | 双向闭环（P15） |

不变的红线：

- Numerics 审计策略 `fact_card` **一字不改**；卡上数字仍是唯一可引用数值；brief 里的任何数字都不是 manifest 成员，模型引用即拒（这正是我们想要的行为）。
- `WEARABLE_90D_SUMMARY` / `PATIENT_STATE_*` / `SUPPLEMENT_BG` / dossier / 工具对 `fact_card_interpret` 继续 forbidden。
- 宪法反硬编码：Python 里不出现指标名、补剂名；不为「某条笔记」打补丁；判定靠 profile 属性、类别、词表。

---

## 3. 总体设计：一个属性、一个槽、一个供给源

```
                  ┌──────────── chat 记忆（用户聊天专属）────────────┐
 Web/Mac 聊天 ──▶ │ chat_sessions / chat_messages / turn_focus /      │
                  │ active_recall / user_health_background_notes      │
                  └───────────────┬──────────────────────────────────┘
                                  │ 只读、去数字、限长（P14）
                                  ▼
                  USER_BACKGROUND_BRIEF（Tier1 · 非数字源）
                                  │
 iPhone 完整卡「生成解读」 ──▶ fact_card_interpret（Tier0 = 卡）──▶ 审计 ──▶ data/fact_card_interpret/*.json
        ▲                         │  memory_write_policy = none（P13）        │
        │                         ✗ 不写任何 chat 表                          │ 解读历史（P15 输入）
        │                                                                     ▼
        └──────────────── CHB 日编译（T0 §Facts + §Background + 解读脉络）◀────┘（P15）
                          USER_BACKGROUND_BRIEF 的供给源由 live notes 切到 CHB 投影
```

- **一个属性**：harness profile 注册表新增 `memory_write_policy`（`chat` | `none`）。`fact_card_interpret = none`。编排器只问这一个谓词，不再散落 `if profile == ...`。
- **一个槽**：新 Tier1 槽 `USER_BACKGROUND_BRIEF`。P14 由 live 背景笔记构建；P15 改由 CHB 投影构建，槽名、契约、审计行为不变。
- **一个供给源**：P15 之后，聊天侧的 `USER_CONTEXT_BRIEF` 与解读侧的 `USER_BACKGROUND_BRIEF` 都从同一份 CHB 工件出，只是投影不同（聊天侧带 §Facts，解读侧不带）。

---

## 4. M1-P13 · 止漏 + 记忆卫生（P0 · bug）

### 4.1 目标

解读轮对以下五张表**零写入**：`chat_sessions`、`chat_messages`、`user_health_background_notes`、`chat_session_turn_focus`、`chat_session_active_recall`；同时不触发 `dynamic_slot_registry` 的 discover/promote、不写 `dynamic_slots.json`。解读结果**只**落 `data/fact_card_interpret/<key>.json`（既有缓存即留痕，P15 读它）。

### 4.2 设计

**(a) 注册表属性**（`pha/harness_profile_registry.py` `_PROFILE_CONTRACTS` + `rules/harness_profile_registry.generated.json`）

- 每个 profile 契约新增 `memory_write_policy`，取值 `"chat"`（默认，所有既有 profile）或 `"none"`。
- `fact_card_interpret` → `"none"`。
- 暴露单一谓词，例如 `profile_writes_chat_memory(profile: str) -> bool`；`resolve_profile_override` 之后即可判定，**在 `create_session` 之前**。
- `scripts/pha_harness_profile_registry_selfcheck.py --write` 重新生成 JSON；registry selfcheck 增加断言：`none` 的 profile 必须同时 `slots_tier1` 不含 `RECALL`/`EPISODIC_BRIDGE`（读写一致性）。

**(b) 编排器「无会话轮」**（`pha/chat_turn_orchestrator.py`）

当 `memory_write_policy == none`：

- 不 `create_session`；`sid` 保持 `None`（或用明确的哨兵对象，禁止用空字符串冒充会话 id，`sid or ""` 的现有写法需要逐处检查它们在 `None` 下是否会误写）。
- 跳过：`append_message`（user 与 assistant 两处）、`maybe_set_title_from_first_message`、`on_request_start` / `on_background_captured`、`maybe_capture_chat_background`、`session_turn_focus.save/consume/revive/clear`、`record_health_turn_focus`、active_recall 写入。
- `_prior_user_msg`、`_existing_focus`、`_route_focus`、`session_focus_row` 取空值；`EPISODIC_BRIDGE` 槽显式置空（不再依赖「恰好为空」）。
- SSE 事件流对调用方**不变**（`status` / `done` / `error` 结构同前，`done.answer.answer_text`、`numerics_audit`、`model` 仍在）；`session_id` 字段如有则为 `null`。
- 实现形态建议：把「会话写入」收敛成一个小的 `TurnMemorySink`（或等价的一组 no-op 函数）在入口按策略选择，避免十几个 `if`。不要求这个形态，但要求**不得**在编排器里写 `== "fact_card_interpret"`。

**(c) 背景捕获防御**（`pha/chat_background.py` `maybe_capture_chat_background`）

- 与 (b) 独立再加一道：内容以 `[` 开头且形如 `[<snake_case_tag>]`（例：`[vision_parse_failed]`）的系统错误串**不入库**；返回 reject 原因 `system_tag_message`。这是通用规则，不是针对 vision。
- 不改 `should_capture_background` 的词表逻辑。

**(d) 记忆卫生脚本**（新 `scripts/pha_memory_hygiene.py`，**默认 dry-run**）

识别三类（用**参数化**的合成消息文本做匹配，从 `harness_plan.FACT_CARD_INTERPRET_USER_MESSAGE` 取现值，旧中文文本作为常量列表 `LEGACY_SYNTHETIC_USER_MESSAGES` 放脚本内，注明来源与日期）：

| 类 | 判定 | 处置 |
|---|---|---|
| A 解读会话 | 会话内**所有** `role=user` 消息 ∈ 合成消息集合 | 删 `chat_messages`、`chat_session_turn_focus`、`chat_session_active_recall`、`chat_sessions` 对应行 |
| B 污染笔记 | `user_health_background_notes.content` 以合成消息前缀开头，或匹配 `^\[[a-z_]+\]` 系统标签 | 删行 |
| C 空会话 | `chat_sessions` 无任何消息 | **默认不删**；`--include-empty` 才删（可能是用户刚点「新会话」） |

要求：

- `--dry-run`（默认）打印每类计数 + 前 5 条样例（会话 id / 时间 / 内容前 60 字）；`--apply` 前先把 DB 复制到 `data/backups/pha_storage.<UTC 时间戳>.db`，打印备份路径；事务内删除；结束再跑一遍统计确认归零。
- 预期 dry-run 量级：A ≈ 56 会话、B ≈ 7 + 17、C ≈ 6。偏差大要停下来问。
- **apply 必须由维护者在对话里确认后再跑**，不得自主执行。

### 4.3 selfcheck（并入 `scripts/pha_fact_card_selfcheck.py`，用临时 DB）

1. 临时库预置 1 个真实会话 + 2 条笔记；mock `stream_fn` 跑 `run_interpretation` 一次 → 五张表行数**逐表相等**，`dynamic_slots.json` mtime 不变。
2. 同一 mock 用 `profile_override="lifestyle"`（对照）→ `chat_sessions` +1、`chat_messages` +2，证明谓词生效而不是管线坏了。
3. `maybe_capture_chat_background("[vision_parse_failed] Server error …")` → 不入库，reject=`system_tag_message`；`"每天补镁 400mg"` → 入库（词表逻辑未被误伤）。
4. registry selfcheck：`fact_card_interpret.memory_write_policy == "none"`，且 Tier1 不含 `RECALL`/`EPISODIC_BRIDGE`。
5. 卫生脚本 dry-run 在临时库上：构造 A/B/C 各 2 条 → 计数正确；`--apply` 后归零，且非目标会话与笔记**一条不少**。

### 4.4 附带发现登记（写 PRD §11，不在本卡修）

- `unstructured_vision` 类别把 vision 解析失败的错误串当作背景入库（17 条）。P13 (c) 只挡新的；根因（vision 失败路径把错误当内容返回）另开卡。
- 6 个空会话来源不明（Web「新会话」未使用即离开的可能性最大），P13 不下结论。

### 4.5 验收与 commit

- 真机/浏览器点一次「生成解读」→ Web 会话列表**不新增**会话；`select count(*) from chat_sessions` 前后相等。
- 解读功能行为不变（audit 通过、缓存命中 `started=False`）。
- commit message 前缀：`fact-card: interpret turn writes no chat memory (M1-P13)`；change-log 一条；PRD §8 P13 → DONE。

---

## 5. M1-P14 · `USER_BACKGROUND_BRIEF` 进解读（A 层 · 产品）

### 5.1 目标

用户在聊天里自述过的补剂 / 用药 / 生活习惯 / 症状，以**非数字源**形态进入 `fact_card_interpret` 的 Tier1，让训练建议能带上「你在服 X / 你最近晚睡」这类个人化注意事项；同时**不引入任何可被引用的数字或日期**，审计策略不动。

### 5.2 不做什么（写进 TASK 与 slot 头）

- 不引用 brief 里任何数值、剂量、日期；不复述剂量；不据此给剂量或处方（FR-6 原则）。
- 与今日卡片无关的背景不提（大纲仍是 `USER_ASSESSMENT_PROMPT`，brief 只影响措辞与注意事项）。
- 不把 brief 当「相关指标对照」的借口（v4 交接的焦点跑偏问题不得回潮）。

### 5.3 槽契约

| 项 | 值 |
|---|---|
| 槽名 | `USER_BACKGROUND_BRIEF` |
| 层级 | Tier1；`fact_card_interpret` 的 `slots_tier1=["USER_BACKGROUND_BRIEF"]`（当前为空列表） |
| forbidden | 不变；`SUPPLEMENT_BG` 继续禁（两者来源同表但内容策略不同，不要复用 `SUPPLEMENT_BG`） |
| 标题（`harness_tier0_assembly` 标题表） | zh `用户背景 · 自述 · 非数字源` / en `User background · self-reported · not a numeric source` |
| 头部导语（块内首行，随 locale） | zh：`以下为用户在对话中自述的补剂、用药、生活习惯与症状，仅用于调整建议的措辞与注意事项。不得引用为数值，不得复述或给出剂量，与今日卡片无关则忽略。` en 同义 |
| 预算 | `PHA_FACT_CARD_BG_BRIEF_MAX_CHARS`，默认 zh 600 / en 900；超限按**整行**截断，永不截半行；头部导语不计入 |
| 开关 | `PHA_FACT_CARD_BG_BRIEF`，默认 `1`；`0` 时槽不出现、缓存键不含 brief 摘要 |
| 降级 | Tier0 预算不足时 Tier1 先整体降级（既有机制）；当前系统提示已 `WARN: tier0_budget_exceeded`（sys≈6170），brief 上线后必须确认 Tier0 四槽**一字不少**，只允许 brief 被裁 |

### 5.4 构建器（新模块，建议 `pha/fact_card_background_brief.py`；不改 `chat_background.py` 的写入逻辑）

输入：`list_background_notes(uid, limit=…)`（既有读函数，limit 取足够大，例如 200）。

处理流水（顺序固定）：

1. **过滤**：只保留 category ∈ {`supplement`,`medication`,`sleep_lifestyle`,`symptom`,`general`}；排除 `unstructured_vision`；排除内容匹配 `^\[[a-z_]+\]`（系统标签）或 ∈ 合成消息集合（P13 清理后应为空，此处是防御）。
2. **去重**：按「去空白、去标点、小写」后的内容归一去重，保留最新。
3. **配额**：每类保留最新 N 条，默认 supplement 6 / medication 4 / sleep_lifestyle 3 / symptom 3 / general 2（env 可调，`PHA_FACT_CARD_BG_BRIEF_QUOTA` JSON）。
4. **去数字**（核心）：
   - **保留**字母与数字紧邻、中间无空白的标识符（`D3`、`B12`、`Omega-3`、`CoQ10`、`SpO2`）——与 FR-6.10「标识符里的数字不计」同一判据。
   - **删除**其它所有数字 token（阿拉伯数字、含小数、范围、以及紧随的单位 `mg|g|mcg|μg|IU|ml|粒|片|次|小时|h|点|%` 等），替换为 `〔数值略〕` / `[amount omitted]`；连续多个替换合并为一个。
   - **删除**日期与时刻表达（ISO、`9月7日`、`Sep 7`、`22:30` 等），不替换直接删。**不输出 `note_date`**；时间语义只允许相对词，且由 `note_date` 与 `as_of` 的差**映射成词表**（`近一周内`/`近一月内`/`更早`；en `within the last week`/`month`/`earlier`），词表放语言表，Python 不写中文。
   - 中文数字（`三粒`、`两次`）也删；词表同样放语言表。
5. **后验**：把去数字后的 brief 交给 **审计用的同一套数字抽取器**（`numerics_manifest` 里对回复做 token 化的函数；如未暴露则以最小改动暴露一个只读函数，不改审计策略），断言无 S 级可引用数字 token 残留；有残留则**整行丢弃**并计 telemetry `bg_brief_line_dropped`。这是「不靠正则赌运气」的保险。
6. **渲染**：按类分小节，每行 `- <内容>（<相对时间词>）`；返回 `(text, meta)`，`meta = {"notes_used": n, "lines_dropped": k, "digest": sha256(text)}`。

`chat_turn_slots.py`：仅当 `"USER_BACKGROUND_BRIEF" in plan.slots_tier1 and flag` 时构建并放入 `ctx.slot_contents`；`fact_card_interpret` 分支仍保持 `background_block=""`、`recalled_snippets=""`、`episodic_bridge_block=""`（P13 已显式）。

### 5.5 TASK 与 soul 的最小改动

- `_FACT_CARD_INTERPRET_TASK`（`pha/harness_plan.py`）增**一条**（作为第 5 条或并入第 2 条末尾，中英文模板各一处）：  
  `USER_BACKGROUND_BRIEF, if present, only shapes cautions and wording of advice. Never cite it as data, never restate or infer doses, and skip it when unrelated to the rows the assessment named.`
- `PHA_FACT_CARD_SOUL_MINIMAL` **不改**。
- TASK 变化会自动使旧缓存失效（键含 TASK 哈希），符合预期。

### 5.6 缓存键与响应元数据

- `interpret_cache_key` 新增入参 `bg_brief_digest`（flag 关时为空串）。用户在聊天里新增一条补剂自述 → 摘要变 → 旧解读不命中。FR-6.5 的键定义同步补一项。
- `_decorate_interpretation` / API 响应新增 `background_used: bool`、`background_notes_used: int`。
- `/proactive/fact-card/view` 解读区块在模型名旁加一行小字（`fact_card_copy` 语言表）：zh `已参考你在对话中自述的 N 条背景（不作为数值来源）` / en 同义；`N=0` 不显示。

### 5.7 selfcheck（并入 `scripts/pha_fact_card_selfcheck.py`，临时 DB + mock stream 抓系统提示）

1. 预置笔记 `每晚补镁 400mg，最近两周都 1 点后睡`（supplement/sleep）、`在吃维生素D3 和 Omega-3`（supplement）、`2026-09-01 开始每天两次鱼油`（supplement）→ brief **含** `镁`、`维生素D3`、`Omega-3`、`鱼油`，**不含** `400`、`1 点`、`2026`、`两次`、任何 `note_date`；含相对时间词。
2. 后验抽取器对 brief 返回 0 个 S 级 token。
3. 抓到的系统提示：Tier1 出现 `USER_BACKGROUND_BRIEF` 标题；`SUPPLEMENT_BG` / `RECALL` / `EPISODIC_BRIDGE` / `WEARABLE_90D_SUMMARY` 均不出现；Tier0 四槽完整。
4. 预算：塞 40 条笔记 → 输出 ≤ 上限，最后一行完整（不以半句或 `〔` 结尾）。
5. flag `0` → 槽不出现，`background_used=false`，缓存键与 flag `1` 时**不同**。
6. 笔记变更 → `interpret_cache_key` 变；笔记不变 → 键不变（幂等）。
7. **审计不放松**：mock 回复写 `你每晚补镁 400mg` → 审计仍拒（`400` 不在 manifest）。这条是防止有人顺手把 brief 数字加进 manifest。
8. 一条 `unstructured_vision` / `[vision_parse_failed]` 笔记 → 不进 brief。

### 5.8 运行验收（真卡、真 prefs、`qwen3:14b`）

在 `/tmp` 用 in-process 方式（参考 v4 交接 §1.3 的做法：直接调 `run_interpretation`，不走 HTTP、不动缓存目录）中英各 3 轮：

| 检查 | 通过线 |
|---|---|
| 数字审计 | 6/6 通过 |
| brief 被引用为数值 / 出现剂量 | 0/6 |
| 出现 `〔数值略〕` 字面被模型复述 | 0/6（出现则改导语措辞，不改审计） |
| 训练建议带上与卡上点名指标**相关**的背景注意事项 | ≥4/6（定性，记录原文） |
| 未点名行另起段落（v4 §5 口径） | ≤1/6 |
| 中文回复出现英文导语残留 / 英文回复出现中文 | 0/6 |

任何一项不达线：先看是 brief 内容、TASK 措辞还是配额问题，按 v4 交接 §6 的原则「不调审计、不加 label 过滤」。验收表贴 change-log。测完**恢复 prefs 原文**。

### 5.9 commit

`fact-card: USER_BACKGROUND_BRIEF tier1 slot for interpret (M1-P14)`；PRD FR-6.8 备注 + FR-6.12 → 已落地；§8 P14 → DONE；change-log。

---

## 6. M1-P15 · CHB 统一供给（C 层 · 闭环）

### 6.1 目标

把「用户长期使用形成的宝贵数据」从 13k 条原始消息变成**编译过、去噪、可审计**的长期画像，并让聊天侧与解读侧都从这一份画像取背景。P14 的槽名与契约不变，只换供给源。

### 6.2 现状

`pha/chb_compiler.py` 已有：T0 §Facts 编译（lab + wearable）、`§Interpretation` 可选 LLM、`recompile_chb_if_stale`、工件 `reports/chb/<uid>/brief_<hash>.json`、Tier1 槽 `USER_CONTEXT_BRIEF`（仅 `lifestyle` / `combined_review`）。**但从未被触发**（`chb_briefs` 0 行、工件目录为空）。

### 6.3 设计

**(a) 编译输入扩展**

- 新增 `§Background`：来源 = P14 构建器的**同一函数**（去数字、配额、后验），`prov_type=user_statement`；**不进 §Facts**（`t0_gated_adopter` 对 `user_statement` 的默认 veto 保持）。
- 新增 `§Interpretation lineage`：读 `data/fact_card_interpret/*.json` 中 `status=done` 且审计通过、近 30 天的条目，取 `calendar_day` + 正文；经同一去数字器后**只保留反复出现的注意事项/建议倾向**（实现可以简单：按句去重 + 频次 ≥2 才保留；不引入 LLM）。这是「主动解读历史 → 长期画像」的回路。
- `ledger_hash` 改为 `ledger_hash + background_hash + lineage_hash` 的组合（或新增 `input_hash`），`chb_stale_status` 用组合值判 stale；否则用户新增自述不会触发重编译。

**(b) 触发**

- 每日一次：在 `GET /proactive/fact-card`（捷径每日必打）返回后，后台线程调 `recompile_chb_if_stale(uid)`；env `PHA_CHB_AUTOCOMPILE`（默认 `1`）；同日只跑一次（标记文件 `reports/chb/<uid>/.last_compile_day`）；失败只记日志，**永不**影响卡片响应。
- 不用 cron / launchd 另起进程（启动共识范围，别碰）。

**(c) 投影**

- `build_user_context_brief_block(uid, profile=…)` 按 profile 投影：
  - `lifestyle` / `combined_review`：现有行为（§Facts + §Interpretation）。
  - `fact_card_interpret`：**只** §Background + §Interpretation lineage，**绝不**带 §Facts（§Facts 有卡外数字，模型引用即被拒，等于给模型埋雷）。
- `USER_BACKGROUND_BRIEF` 构建器改为：CHB 工件新鲜（同日或 `is_stale=False`）→ 用投影；否则回落 live notes（P14 逻辑）。`meta.brief_source ∈ {"chb","live_notes"}` 进响应元数据与 telemetry。
- `USER_CONTEXT_BRIEF_PROFILES` **不**加 `fact_card_interpret`——解读侧走的是 `USER_BACKGROUND_BRIEF` 槽，不要两个槽同时出现。

### 6.4 selfcheck（扩 `scripts/pha_chb_compiler_selfcheck.py` + `pha_fact_card_selfcheck.py`）

1. 临时库 + 临时 `reports/chb`：编译后工件含 `§Background`，且 §Background 经后验抽取器 0 个 S 级 token。
2. 新增一条自述 → `chb_stale_status.is_stale=True`；重编译后 `False`。
3. `fact_card_interpret` 投影**不含** §Facts 任何一行；`lifestyle` 投影含。
4. 工件缺失 → `brief_source=live_notes`；工件新鲜 → `chb`；两种源产出的 brief 都通过 P14 的 7 条断言。
5. lineage：造 3 份解读缓存 json（2 份含同一句建议）→ 该句进 lineage；只出现 1 次的不进。
6. 自动编译标记：同日两次触发只编译一次。

### 6.5 验收与 commit

- 运行一天后 `reports/chb/default/` 有工件；`GET /proactive/fact-card` P95 时延不变（编译在后台）。
- 解读响应 `brief_source=chb`；P14 §5.8 表重跑 3+3 仍达线。
- commit：`chb: background + interpret lineage; interpret brief served from CHB projection (M1-P15)`；PRD §8 P15 → DONE；change-log。

---

## 7. 明确不做（本轮）

- B 层（RECALL / turn_focus / EPISODIC_BRIDGE / 上轮摘要）进解读：**不做**，并在 P13 变成显式禁令。
- 把 brief 数字加进 Numerics Manifest / 新增 `user_statement` 审计域：**不做**。
- 改 `fact_card` 审计策略、FR-6.10 分级、`PHA_FACT_CARD_SOUL_MINIMAL`：**不做**。
- 解读结果写回 chat 会话「让用户在聊天里看到」：**不做**（P15 的 lineage 是编译后进画像，不是回灌原文）。
- vision 失败串入库的根因、6 个空会话来源、`OLLAMA_KEEP_ALIVE`：登记，不在本文修。

---

## 8. 风险与对策

| 风险 | 对策 |
|---|---|
| 去数字器漏网 → 模型引用 → 审计拒 → 用户看到「未生成」 | 后验抽取器整行丢弃（§5.4 第 5 步）；审计不放松是底线，宁可少一行背景 |
| 模型复述 `〔数值略〕` 字面 | 导语已要求「不得复述」；验收 §5.8 有专项；不达线改导语措辞 |
| 14b 上 brief 加剧焦点漂移（讨论未点名指标） | TASK 第 5 条限定「只影响措辞与注意事项」；验收沿用 v4 口径 ≤1/6 |
| Tier0 预算本已超（sys≈6170）+ brief → Tier0 被裁 | 验收断言 Tier0 四槽一字不少；必要时先把 `FACT_CARD_CONTEXT` 的 JSON `indent=2` 改紧凑（另议，不在本文） |
| 卫生脚本误删用户真实会话 | 判定为「**所有** user 消息 ∈ 合成集合」；C 类默认不删；apply 前备份 + 维护者确认 |
| CHB 后台编译撞 SQLite 写锁 | 编译只读 DB，写的是 json 工件；标记文件同日一次 |

---

## 9. 交付清单（逐卡）

| 卡 | 代码落点 | 文档落点 |
|---|---|---|
| P13 | `harness_profile_registry.py` + `rules/*.generated.json`；`chat_turn_orchestrator.py`；`chat_background.py`；新 `scripts/pha_memory_hygiene.py`；`pha_fact_card_selfcheck.py`、`pha_harness_profile_registry_selfcheck.py` | PRD §8 P13 DONE、§11 两条附带发现；`pha-ios-proactive-change-log.md`；`harness-change-log.md`（registry 属性） |
| P14 | 新 `pha/fact_card_background_brief.py`；`harness_plan.py`（TASK 一条 + Tier1）；`chat_turn_slots.py`；`harness_tier0_assembly.py`（标题）；`fact_card_interpret.py`（缓存键、meta）；`fact_card_api.py` / `fact_card_copy` / view 模板；语言表（相对时间词、单位词、导语） | PRD FR-6.8 备注、FR-6.12 落地、FR-6.5 键定义；§8 P14 DONE；两份 change-log；验收表 |
| P15 | `chb_compiler.py`（§Background / lineage / 组合 hash / 投影）；`fact_card_api.py`（后台触发）；`fact_card_background_brief.py`（供给源切换）；两份 selfcheck | PRD §8 P15 DONE；change-log |

每卡 commit 后 `git status` 干净；push 由维护者执行（PRD §9 第 7 条）。
