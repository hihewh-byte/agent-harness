# 交接 · 事实卡解读焦点跑偏：profile 专用 soul（M1-P9.5）

> 写给接替的 coding agent · 2026-09-08 22:45 起笔 · 依据 9/8 22:26–22:29 三次英文 API 复测（`enR1–enR3`）与 zh-2/zh-3 对照  
> 首条回复必须同时输出两行：  
> `CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`  
> `CONSENSUS_ACK: harness-opus48-v2026-06-08 read`  
> 真源：[`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) v1.10（FR-6.8 整卡是证据源 / §8）· [`pha-pm-constitution.md`](pha-pm-constitution.md)（反硬编码、禁止对特定用例打补丁）· 上一份交接 [`handoff-2026-09-08-fact-card-interpret-v3-numerics.md`](handoff-2026-09-08-fact-card-interpret-v3-numerics.md)（§4.3「大纲在 TASK、不解析指标 id」仍有效，本文不推翻）  
> 本文**只含设计，不含代码**。改动面很小（一个常量、一个分支、一个哈希入参、三条 selfcheck），不要扩大。

---

## 0. 现场状态与开工顺序

**git**：`main` 领先 `origin/main` 两个 commit（`95f8e5b`、`eafe393`），未推送。工作区**脏**：`pha/numerics_manifest.py`、`scripts/pha_numerics_manifest_selfcheck.py`、`docs/pha-ios-proactive-change-log.md`、`docs/harness-change-log.md`——这是 M1-P9.4.1（英文无年日期遮罩，策略 `v1.1`），已复测通过但**未提交**。

开工顺序：

1. 先把 P9.4.1 单独提交（message 见 §9），`git status` 干净后再动本文任何一处。不要把两件事混进一个 commit。
2. 读 §1 证据，自己用 §1.3 的方法在本机复现一次（看系统提示第一条消息里有没有「三步看诊法」）。
3. 按 §3 → §4 → §5 顺序做，每步 selfcheck 绿再下一步。

**运行时**：PHA 在 `:8788`，build `pha-v2.3.32-full-import-only-p94`；ingest token 在 `~/Library/Application Support/pha/env-8788.sh`；重启用 `bash scripts/pha_restart_accept.sh`。当前 `data/fact_card_prefs.json` 为 zh-CN，评估要求原文：`只看静息心率与HRV，VO2Max。用一两段话说清楚这样的数值对于今天的运动训练有哪些建议，比如运动类型运动强度的建议`。测试改过之后**必须原样恢复**。

---

## 1. 问题与根因

### 1.1 现象

评估要求点名「只看 RHR / HRV / VO2max」，卡上还勾着 active_energy / respiratory_rate / spo2。同模型 `qwen2.5:7b-instruct`：

| 轮次 | 语种 | 审计 | 提到 SpO2 / 呼吸率 | 段落标题 |
|---|---|---|---|---|
| zh-2 | zh-CN | 过 | 否（漂到「睡眠」） | 无 |
| zh-3 | zh-CN | 过 | 否 | 无 |
| enR1 | en-US | 过 | **是** | `Trend review / Related markers / Recommendations` |
| enR2 | en-US | 过 | **是** | 同上 |
| enR3 | en-US | 过 | **是** | 同上 |

数字审计全过（那些数本来就在卡上），所以这不是审计问题，是**大纲被覆盖**。

### 1.2 根因（代码证据）

三段标题一字不差来自 `pha/chat_message_stack.py` `PHA_MEDICAL_SOUL_SYSTEM_PROMPT` 的「三步看诊法」（第 43–52 行）。第二步原文：

> 【相关指标对照（Related Markers）】：可横向对照当轮证据中的相关穿戴/化验指标……

而 `pha/chat_turn_slots.py` 第 557–570 行按 profile 选 soul：

- `is_attachment_qa_profile` → `PHA_ATTACHMENT_SOUL_MINIMAL`（明文「no three-step clinical review structure」）
- `is_wearable_screenshot_profile` → `PHA_WEARABLE_SOUL_MINIMAL`（明文「do not use the three-step clinical review headings」）
- **其它（含 `fact_card_interpret`）→ `else` → 完整医疗 soul**

`fact_card_interpret` 的 TASK 说 "If it names metrics, discuss only those rows"，但 TASK 在 Tier0 补充层，soul 在它上面。模型是在**服从**更高层「必须横向对照其它指标」的指令。中英文吃同一个 soul，机制两边都有；中文样本少且 zh-2 也漂了，「中文不跑偏」不成立，只是概率低一点。

### 1.3 复现方法（不进仓库）

在 `/tmp` 用 Python 走 `chat_turn_slots` 里给 `fact_card_interpret` 建槽的入口（`plan.profile == "fact_card_interpret"`，`authoritative_profile` 同名），取回 `chat_messages[0]["content"]`，`grep` `三步看诊法` / `Related Markers`。应能命中；改完 §3 后应为空。

---

## 2. 设计原则（先判定，再改）

1. **复用既有模式**：按 profile 选 soul 已是 `chat_turn_slots` 的现成机制（两个 profile 在用）。本文只是让第三个 profile 加入，不是新机制。
2. **TASK 是唯一大纲**：soul 只定角色和红线，不定结构。任何「先写什么后写什么」的话都不进 soul。
3. **零指标解析、零审计改动**：不解析评估要求，不按 label 拒，不改 `numerics_manifest`，不改 FR-6.10。焦点是风格/大纲问题，fail-closed 只用于编造。
4. **一次只动一个变量**：本轮**不改 TASK 文本**。先量 soul 单独的效果（§5），不够再走 §6。
5. **反硬编码**：soul 文本里不得出现任何指标名、单位、卡上字段名、T1 模板字面量、中文或英文回复模板。语言交给 `RESPONSE LANGUAGE` 指令（`response_language.py`），与另两个 minimal soul 一致。

### 2.1 已否决的方案（不要再提）

| 方案 | 否决理由 |
|---|---|
| 后验按卡上 label 拒/重试 | 要把自由文本评估要求解析成指标 id，正是 P9.3 撤掉的 alias 匹配；且拒的是卡上真实数字，fail-closed 用错地方 |
| 只加强 TASK 措辞 | 用低层槽位对抗 soul 的强制结构，7b 上无效；治标 |
| 上下文把点名指标置顶 | 同样要解析点名指标 |
| 改 `PHA_MEDICAL_SOUL_SYSTEM_PROMPT` 本身 | 影响全部聊天 profile，超出范围 |

---

## 3. 改动明细

### 3.1 新常量 `PHA_FACT_CARD_SOUL_MINIMAL` — `pha/harness_plan.py`

放在 `FACT_CARD_INTERPRET_USER_MESSAGE` / `_FACT_CARD_INTERPRET_TASK` 旁（该文件已是 fact_card_interpret 常量的归属；`chat_turn_slots` 与 `fact_card_interpret` 都已 import 它）。加进 `__all__`（若有）。

**内容要求**（英文写，风格对齐 `PHA_WEARABLE_SOUL_MINIMAL`，≤ 600 字符）：

- `Role:` 一句：PHA 个人健康助手；本轮**只**按 TASK 解读今日事实卡。
- `Rules:` 逐条：
  1. 语言按 `RESPONSE LANGUAGE` 指令；自然口吻。
  2. **不得**使用三步看诊结构或其任何语言的标题（不列举具体标题字面量之外的指标；可以像 wearable soul 那样举标题名以示禁止）；**不得**自行增加「相关指标 / related markers」一类的横向对照段——大纲只来自 TASK 与 USER_ASSESSMENT_PROMPT。
  3. 数字与日期只来自本轮注入的 FACT_CARD_CONTEXT / Numerics Manifest；不得从 Patient State、快照或记忆取数（这些槽位本轮本就 forbidden，写一句是给模型看的）。
  4. 教育性、非诊断；无处方、无剂量。
  5. 纯文本，不用 Markdown。
  6. 不暴露内部术语（Tier0、Manifest、metric_id、ledger、verdict 等）。
  7. 不重复免责声明（页面已有）。

**禁止出现**：任何指标名/缩写（`HRV`、`SpO2`、`静息心率`…）、单位、卡字段名、`【参考标准` / `[Reference Standard`、中文句子。selfcheck 会锁这些（§4）。

### 3.2 soul 选择分支 — `pha/chat_turn_slots.py` 第 557–570 行

把现有 `if / elif / else` 链抽成一个纯函数（建议名 `select_soul_base(profile: str, qtype) -> Optional[str]`，放同文件），行为对其它 profile **逐字不变**，新增一条：

```
attachment → PHA_ATTACHMENT_SOUL_MINIMAL
wearable_screenshot → PHA_WEARABLE_SOUL_MINIMAL
profile == "fact_card_interpret" → PHA_FACT_CARD_SOUL_MINIMAL      ← 新增
qtype == CASUAL → PHA_MEDICAL_SOUL_LITE_SYSTEM_PROMPT
其它 → None（沿用完整医疗 soul）
```

判定用 `plan.profile == "fact_card_interpret"`，与该文件第 274/279/321/394 行既有写法一致；不要新造 `is_fact_card_profile` 之类的模糊前缀匹配。

`ctx.soul_base` 下游（第 570、573、606 行，以及 `chat_turn_orchestrator.py:689`）不需要改：它们已经消费 `soul_base`。

### 3.3 缓存键 — `pha/fact_card_interpret.py::_interpret_prompt_rev`

现在哈希 `TASK(en) | FACT_CARD_AUDIT_POLICY_REV`。加入 soul 文本：`TASK(en) | POLICY_REV | PHA_FACT_CARD_SOUL_MINIMAL`。这样 soul 一变旧解读自动不命中，不用手清缓存；也是 §4 的一条断言。

### 3.4 `pha/harness_report.py:740`（可选，一致性）

该处无条件用 `PHA_MEDICAL_SOUL_SYSTEM_PROMPT` 拼系统提示。先确认 `fact_card_interpret` 是否经过这条路径（它是 report/replay 装配）。若经过，改为同样调用 `select_soul_base`；若不经过，不改，只在 change-log 记一句「report 路径仍用完整 soul，与在线路径不一致，待并轨」。不要为此扩大改动。

### 3.5 不改的东西

- `_FACT_CARD_INTERPRET_TASK` 文本（本轮不动，见 §2 第 4 条）。
- `harness_tier0_assembly` 的槽序、`harness_profile_registry` 的 slot invariants（soul 不是槽位，`--write` 产物应无 diff）。
- `numerics_manifest.py`、`fact_card_copy.py`、HTML/API。
- `strip_markdown_markers`（标题消失应靠 soul 本身，不靠后处理）。

---

## 4. selfcheck（先写用例，再实现）

### 4.1 `scripts/pha_fact_card_selfcheck.py`

在现有 TASK 断言（约第 1104–1112 行）附近加：

1. **soul 路由**：`select_soul_base("fact_card_interpret", <非 CASUAL qtype>)` 返回的对象 `is PHA_FACT_CARD_SOUL_MINIMAL`；`select_soul_base("wearable_screenshot_review", …)` 与 `select_soul_base("attachment_asset_qa", …)` 返回值与改前相同（回归门）；任意其它 profile 返回 `None`。
2. **系统提示不含三步法**：用 §1.3 的入口拿 `chat_messages[0]["content"]`，断言不含 `三步看诊法`、`纵向趋势对账`、`Related Markers`、`Trend review`，且含 soul 的 `Role:` 首句。若建槽入口依赖外部服务不便在 selfcheck 里跑，退一步只测第 1 条 + 第 3 条，并在 change-log 说明。
3. **soul 源码反硬编码**：`PHA_FACT_CARD_SOUL_MINIMAL` 不含 `resting_heart_rate` / `静息心率` / `HRV` / `SpO2` / `VO2` / `【参考标准` / `[Reference Standard`，且不含任何 CJK 字符（`re.search(r"[\u4e00-\u9fff]")` 为 None）。
4. **缓存键随 soul 失效**：记录 `_interpret_prompt_rev()`；`monkeypatch` 该常量为另一字符串后再取一次，两者不同；恢复后相同。

### 4.2 `scripts/pha_chat_turn_fsm_selfcheck.py` 与 registry

`fact_card_interpret` 槽序不变；`harness_profile_registry --write` 无 diff。这是「soul 不是槽位」的证明。

### 4.3 `scripts/pha_numerics_manifest_selfcheck.py`

不动，跑一遍全绿即可（确认 §0 第 1 步的 P9.4.1 已入库）。

---

## 5. 运行验收（改后必做，结果贴 change-log）

1. 清空 `data/fact_card_interpret/`；`bash scripts/pha_restart_accept.sh`；`/health` 应显示新 build 号（build_marker 按惯例递增）。
2. **英文 3 轮**：`save_fact_card_locale('default','en-US')`，评估要求用与 enR1–R3 完全相同的句子：`Only resting heart rate, HRV, and VO2max. In one or two paragraphs, explain what these numbers mean for today's training — e.g. workout type and intensity.`；每轮先删缓存再 `POST /proactive/fact-card/interpret`，轮询 `GET` 至 `done|failed`。
3. **中文 3 轮**：恢复 zh-CN 与 §0 的中文原句，同法。
4. 每轮记录（脚本放 `/tmp`，不进仓库）：`status`、`policy_rev`、正文是否出现 `Trend review|Related markers|Recommendations|纵向趋势对账|多指标横向联动|其他相关指标`、是否出现 SpO2/呼吸率（`SpO2|blood oxygen|96\.0|respiratory rate|血氧|呼吸率`）、是否出现「睡眠/sleep」、是否提到 RHR/HRV/VO2max、英文里有无 CJK 泄漏。
5. **通过线**：6 轮审计全过；三段标题 **0/6**；SpO2/呼吸率跑偏 **英文 ≤ 1/3、中文 0/3**；RHR 与 HRV **6/6** 提到。VO2max 漏提是另一个已知问题（模型偶发），只记录不作为本轮门槛。
6. 达线：写 change-log，进 §7。未达线（标题已消失但仍念别的指标 ≥ 2/3）：进 §6，**不要**改审计、不要加 label 过滤。
7. 最后把 prefs 恢复到 zh-CN + 中文原句，`cat data/fact_card_prefs.json` 核对。

---

## 6. 第二步（仅当 §5 未达线才做）

在 `_FACT_CARD_INTERPRET_TASK` 第 1 条末尾加**一句**：不得为用户未点名的行另起段落或句子。要求：不含指标名；中英同一句英文（TASK 本就是英文）。缓存键随 TASK 哈希自动失效。改完重复 §5 的 2–5。仍不达线则停下写 change-log，等维护者拍板（候选：换更大模型、或在 UI 让用户勾选「重点指标」作为结构化输入——后者要改 PRD，不在本文范围）。

---

## 7. 文档改动清单

| 文件 | 改什么 |
|---|---|
| `prd-pha-ios-proactive-agent-v1.md` | §8 加 **M1-P9.5**「解读专用 soul（焦点跑偏）」，状态随验收置 DONE；§11/§12 版本号按惯例 +0.1；FR-6 不改条文，只在 FR-6.8 备注「解读轮不套三步看诊法」 |
| `pha-ios-proactive-change-log.md` | 新条目：类别 P1（解读大纲）；根因（soul 三步法第二步）；改动（常量 + 分支 + 缓存键）；证据（§5 六轮表）；回滚（删 `select_soul_base` 中 fact_card 分支即可，缓存键自动失效） |
| `harness-change-log.md` | soul 选择抽函数、fact_card_interpret 走 minimal soul；`harness_report.py:740` 是否并轨 |
| `handoff-…-v3-numerics.md` | §11 表末追加一行指向本文（「焦点跑偏 → v4」） |

---

## 8. 不要做的事

- 不要解析评估要求里的指标名，不要按 label 拒或重试。
- 不要改 `numerics_manifest.py`、FR-6.10、任何审计逻辑。
- 不要改 `PHA_MEDICAL_SOUL_SYSTEM_PROMPT` 或另两个 minimal soul。
- 不要在 soul 里写指标名、单位、T1 模板、中文句子、输出结构。
- 不要在同一 commit 里同时改 soul 和 TASK（§2 第 4 条）。
- 不要把 `/tmp` 的评分脚本或正则放进仓库。
- 不要永久改动 `data/fact_card_prefs.json`。

---

## 9. commit 计划

- **commit A（先做，P9.4.1，现有脏工作区）**：  
  `Fact-card audit: yearless EN/CN month-day dates resolve to card dates (policy v1.1)`  
  正文两行：`_extract_fact_card_dates` + surface-form masks；selfcheck `FC-en-yearless-ok/bad`。
- **commit B（本文，P9.5）**：  
  `Fact-card interpretation: dedicated minimal soul; no three-step review structure`  
  正文：`select_soul_base` 抽函数；`PHA_FACT_CARD_SOUL_MINIMAL`；cache key includes soul；selfchecks；docs。
- 若走了 §6：**commit C** 单独：`Fact-card TASK: no sections for unnamed rows`。

三个 commit 都不推送，维护者自己 push。

---

## 10. 需要维护者拍板（附默认值，未回复即按默认执行）

| # | 问题 | 默认 |
|---|---|---|
| 1 | soul 常量放 `harness_plan.py` 还是新建 `fact_card_harness.py` | `harness_plan.py`（常量已聚在那里，少一个文件） |
| 2 | `harness_report.py:740` 是否本轮并轨 | 仅当 fact_card 路径经过它才改；否则记 change-log 待办 |
| 3 | §5 通过线「英文 ≤ 1/3」是否太松 | 保留；两周真机后按 telemetry 再收 |
| 4 | §6 触发后是否允许直接做 | 允许，但单独 commit 且 change-log 单独条目 |
