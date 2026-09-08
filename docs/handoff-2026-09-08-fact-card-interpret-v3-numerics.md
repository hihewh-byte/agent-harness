# 交接 · 事实卡解读数字审计 v3：卡外数字分级放宽 + 单一审计 + review 优化清单（M1-P9.4）

> 写给接替的 coding agent · 2026-09-08 20:10 起笔 · 依据 9/8 17:06 / 17:07 真机截图（解读连续被拒 `2、95、2、3、95` / `70、80、2、2、95、2、3`）与本机复现  
> 首条回复必须同时输出两行：  
> `CONSENSUS_ACK: pha-ios-proactive-prd-v1 read`  
> `CONSENSUS_ACK: harness-opus48-v2026-06-08 read`  
> 真源：[`prd-pha-ios-proactive-agent-v1.md`](prd-pha-ios-proactive-agent-v1.md) **v1.10**（FR-6.3 / FR-6.10 / §8 M1-P9.4 / §11）· [`manifest-tier-v1.md`](manifest-tier-v1.md) §3.2 / §4（T0 优先于 T1、T1 披露协议）· [`pha-pm-constitution.md`](pha-pm-constitution.md)（反硬编码、禁止对特定用例打补丁）  
> **维护者已授权**（2026-09-08 20:11）：卡外数字审计 **可以放宽**，尺度由本文 §2 定；本文只落文档与开发指导，**不含代码**。  
> 上一份交接：[`handoff-2026-09-08-fact-card-interpret-v2.md`](handoff-2026-09-08-fact-card-interpret-v2.md)（§4.4「卡侧审计重做」被本文 §3 取代）

---

## 0. 开工前必读与现场状态

必读顺序：PRD v1.10 全文 → `manifest-tier-v1.md` §3–§4 → harness 共识 §5 → `harness-change-log.md` / `pha-ios-proactive-change-log.md` 各最近三条 → 本文。

**git 现场**：`main` 领先 `origin/main` 一个 commit `8462695`（未推送）。该 commit 的正文与 message 描述的是「评估要求→指标 id 别名解析→收窄 manifest→拒焦点外数字」这一刀，已被维护者判定为 corner case、违反宪法第四条与 FR-6.8；工作区已撤回并改为 TASK 大纲（见 change-log 9/8 两条）。**工作区仍是脏的**（9 个文件 modified），不要 stash / checkout 丢弃。历史整理见 §7。

**复现方法（不写进仓库）**：在 `/tmp` 用 Python 载入 `load_fact_card('default')`，把 §2.4 表里的句子逐条喂给 `fact_card_interpret._audit_interpretation_text`，可以得到与截图相同的 token；同一批句子喂 `numerics_manifest.audit_response_numerics` 全部 `passed=True`。这就是「两道审计结论相反」的直接证据。

---

## 1. 问题证据（为什么要动）

| 截图 token | 实际来源 | 性质 |
|---|---|---|
| `2`（每段都出现） | `SpO2` / `VO2max` 标签里嵌的数字。卡侧 `_NUM_RE = \d+(?:\.\d+)?` 无任何边界；卡上自己的标签也会触发 | 审计假阳性 |
| `96.0`（本机复现） | `FACT_CARD_CONTEXT` 给模型的是 JSON 原值 `"value": 96.0` / `13.0`，而白名单只有 `96` / `13`。模型照抄卡也被拒 | 我们自己两处格式不一致 |
| `95`、`70`、`80`、`3` | 科普/建议数字：血氧 95% 常见阈值、最大心率 70–80% 区间、每周 2–3 次 | 按 FR-6.10 v1.7 必须进 T1 块；7b 写不出精确模板 |
| `9` | 疑似「9 月」；失败记录不存原文，无法确认 | 可观测性缺口 |

两道审计规则不同：

| | harness `numerics_manifest.audit_response_numerics` | 卡侧 `fact_card_interpret._audit_interpretation_text` |
|---|---|---|
| 抓什么数 | 1–2 位小数（前后非数字锚定）+ 剂量语境数 + 3–6 位裸整数 | 所有 `\d+(\.\d+)?`，无边界 |
| T1 块 | `LANG_DISCLOSURE_MAP` 中英双语 | 只认中文 `【参考标准】…（来源：…，请自行查证…）` |
| `.0` 归一 | 白名单按格式化字串 | 无 |
| 个人主张语境 | 有（`LANG_T0_CLAIM_MAP`，T0 优先于 T1） | 无 |
| 对同一段文本 | `passed=True` | 拒 |

结论：屏幕上的「反复不通过」= 卡侧假阳性 + 7b 不会写 T1 模板 + 双审计并存。**不是模型在编个人数据**。

---

## 2. 决策：卡外数字分级（放宽尺度）

### 2.1 原则

- 守住的东西不变：**看起来像用户测量值/日期的数字，永远只能来自白名单**（PRD §1「数值诚实与 fail-closed 优先」）。
- 放开的东西：**一般人群常识、训练建议里的整数**，不再强制进 T1 块、不再强制写来源。T1 块保留为「想给来源时」的推荐形式，块内规则不变。
- 判定用 **语境**，不用 **数值大小**（撤掉 ≥100 阈值的教训）；语境词表放语言表，指标标签/单位来自卡，**Python 不出现任何指标名**。
- 拿不准 → 拒（fail-closed）。

### 2.2 术语

| 名词 | 定义 |
|---|---|
| 白名单 W | 由整张卡生成的 manifest：各行 `value` / 基线均值 / 参考范围低高 / 基线 n / 窗口天数（`90d`→90、`365d`→365、文案常量 7、12 —— 后两者应由卡的窗口字段派生，见 §3.3）/ `as_of` / `calendar_day` / 各行 `day` / 卡上时刻。数值 **归一化后**比对：`96.0 ≡ 96`，`6,484 ≡ 6484`，全角数字转半角 |
| T1 块 | `manifest-tier-v1` §4 披露块，中英两种形态（`LANG_DISCLOSURE_MAP`）。块内数字不验真伪；块内出现个人主张词 → `t0_forgery_in_t1_block` |
| 标识符数字 | 数字与字母/下划线**紧贴**（`SpO2`、`VO2max`、`T1`、`HRV4`）。不是数字 token，不计 |
| 子句 | 剥掉 T1 块、遮掉日期/时刻/标识符后，按 `。！？；，` 与 `. ! ? ; ,` 切开的片段 |
| 个人主张语境 P | 子句含 **归属词**（你 / 你的 / 您 / your / yours）或 **时间归属词**（今天 / 今晨 / 昨天 / 昨夜 / 本周 / 上周 / 近 N / 最近 / 过去 / today / tonight / yesterday / this week / last N / recent）或 **测量动词**（测得 / 记录 / 显示 / 读数 / 卡上 / 均值 / 中位 / 基线 / measured / recorded / shows / reading / baseline / median） |
| 教育语境 E | 子句含 **人群词**（一般 / 通常 / 常见 / 多数人 / 健康成年人 / 人群 / typical / usually / most adults / general population）或 **建议词**（建议 / 推荐 / 可以 / 尽量 / 控制在 / 保持在 / 目标 / 不超过 / recommend / aim for / keep / try to / target / up to）或 **参考词**（参考 / 范围 / 区间 / 阈值 / 指南 / reference / range / threshold / guideline） |
| 卡指标语境 M | 子句含卡上任一行的 `label`（当前 locale 与另一 locale 的 label 都算）或 `unit`（bpm / ms / % / kcal / mL/kg/min / 步 / 小时 …，全部来自 manifest 行，不写死） |

### 2.3 判定规则（对每个白名单外的数字 token）

```
0. token 在 T1 块内            → 放行（块内另跑 t0_forgery 扫描）
1. token 是日期/时刻            → 必须 ∈ W，否则 unauthorized_date / unauthorized_time
2. token 带 1–2 位小数（归一后仍非整数） → 必须 ∈ W，否则 unauthorized_value（S 级）
3. 子句 ∈ P                    → 必须 ∈ W，否则 unauthorized_value（S 级）
4. 子句 ∉ P 且 ∈ E             → 放行，记 educational_int（E 级，进 telemetry 不进 violations）
5. 子句 ∉ P 且 ∉ E 且 ∈ M       → 拒 unauthorized_value（歧义，fail-closed）
6. 其余（无归属、无教育词、无卡指标标签/单位的裸整数） → 放行，记 educational_int
```

规则 2 是本次放宽里**唯一保留的「按形态」规则**：可穿戴域的小数几乎只可能是测量值（HRV 32.9、睡眠 7.6h），教育数几乎都是整数或「约」。想写「建议 7.5 小时」的模型要么写「7 到 8 小时」，要么进 T1 块。这是有意为之，写进 TASK。

### 2.4 样例（直接变成 selfcheck 用例；「当前」= 现卡侧审计结果，复现自本机）

| # | 文本 | 当前 | v3 期望 | 命中规则 |
|---|---|---|---|---|
| 1 | 今天血氧 96.0%，SpO2 处于正常范围。 | 拒 `96.0`,`2` | 过 | `.0` 归一；`SpO2` 是标识符 |
| 2 | 你的 VO2max 51.5 mL/kg/min 与近 12 个月 129 天持平。 | 拒 `2` | 过 | 标识符 |
| 3 | 一般成年人血氧饱和度高于 95% 视为正常。 | 拒 `95` | 过（E） | 规则 4：人群词 |
| 4 | 建议每周进行 2–3 次中低强度有氧运动。 | 拒 `2`,`3` | 过（E） | 规则 4：建议词 |
| 5 | 训练心率控制在最大心率的 70–80%。 | 拒 `70`,`80` | 过（E） | 规则 4：建议词「控制在」 |
| 6 | 你的血氧 96%，高于常见的 95% 阈值。 | 拒 `95` | 过 | 子句切分：第二子句 ∉ P、∈ E |
| 7 | 今天 HRV 32.9 ms，昨天 40 ms。 | 拒 `40` | 拒 `40` | 第二子句含「昨天」∈ P |
| 8 | 静息心率 65 bpm 偏高。 | 拒 `65` | 拒 `65` | 规则 5：卡标签+单位，无教育词 |
| 9 | 静息心率一般在 60–100 bpm。 | 拒 `60`,`100` | 过（E） | 规则 4 优先于规则 5 |
| 10 | 你的 HRV 接近 35 ms。 | 拒 `35` | 拒 `35` | 规则 3（卡上是 32.9） |
| 11 | 建议睡 7.5 小时。 | 拒 `7.5` | 拒 `7.5` | 规则 2：小数 |
| 12 | 【参考标准】血氧常见正常范围 95% 以上（来源：WHO，请自行查证，非医疗建议） | 过 | 过 | T1 块 |
| 13 | 【参考标准】血氧常见正常范围 95% 以上（来源：WHO） | 拒 `95` | 过（E） | 块不完整→退化为普通文本，但子句 ∈ E |
| 14 | [Reference Standard] SpO2 above 95% is typical (source: WHO, verify by yourself, not medical advice) | 拒 `2`,`95` | 过 | 英文 T1 块 + 标识符 |
| 15 | Your resting heart rate today is 63 bpm; adults usually sit between 60 and 100. | 拒 `60`,`100` | 过 | 子句切分 + E |
| 16 | 【参考标准】你的血氧 94% 偏低（来源：WHO，请自行查证，非医疗建议） | 过 | 拒 `t0_forgery_in_t1_block` | 块内归属词 |
| 17 | 近 90 天睡眠均值 7.6 小时。（卡为 365d） | 拒 | 拒 `unauthorized_window:90` + `7.6` | FR-6.8 窗口一致性保留 |
| 18 | 2026-09-05 的静息心率是 60。（卡无该日） | 拒 | 拒 `unauthorized_date` | 规则 1 |

### 2.5 明说的取舍

- **接受的漏网**：无归属、无标签、无单位的裸整数（「偏高的 65」）会按 E 放行。这种句子对读者也构不成可读的个人数据主张；telemetry 记 `educational_int`，若真机出现明显编数再收。
- **不采用**「整句」为判定单位：整句会把「你的血氧 96%，高于常见的 95%」全部判 P，等于没放宽。子句切分是放宽落地的关键。
- **不采用** 数值大小阈值、不采用「只放行 ≤ 2 位整数」之类形态规则（都是历史上被撤掉的做法）。
- **不采用** 每次失败自动重试：FR-6.6 要求失败态可见。自动修复轮（把 violations 回灌）作为 P9.4b 备选，见 §10。

---

## 3. 架构决策：一道审计，规则住在一个地方

### 3.1 归属

- **规则与词表的唯一 owner**：`pha/numerics_manifest.py`。新增一个按 profile 生效的 **fact-card 策略**（命名建议 `fact_card` policy / `audit_scope`），实现 §2.3 六条。现有 `_audit_response_numerics_strict` / `_t0_plus_disclosure` 不改语义，只在 `audit_response_numerics` 入口按 `manifest.profile == "fact_card_interpret"` 分派。
- **词表**：`LANG_T0_CLAIM_MAP` 扩两组键 `temporal_cues`、`educational_cues`（中英各一份，与现有 `owner_cues` 同风格）。`metric_cues` 不再用于事实卡路径——卡指标语境 M 由 manifest 行的 `label` / `unit` 动态生成。**`fact_card_interpret.py` 里不允许再出现任何中文或英文字面量正则**（`_T1_BLOCK_RE`、`_NUM_RE` 等全部删除）。
- **T1 块**：复用 `LANG_DISCLOSURE_MAP`，中英同权。
- **标识符遮罩**：一条通用正则（数字前或后紧贴 `[A-Za-z_]` 即整段遮掉），不是 `SpO2|VO2max` 列表。
- **归一化**：在 manifest 构建期把每个值同时登记「格式化字串」与「归一字串」（`96.0`→`96`），审计端对 token 也做同样归一后再比对；千分位、全角数字在同一函数处理。

### 3.2 卡侧只剩什么

`fact_card_interpret._audit_interpretation_text` 收缩为：

1. 调 `audit_response_numerics(text, manifest)`（manifest 就是 harness 这轮用过的那一份，由 `chat_service` 回传；不重新生成）。
2. **仅保留卡专有维度**：窗口措辞一致性（FR-6.8：「近 90 天」对 365d 卡 → `unauthorized_window:90`）。这一条也应尽量下沉：manifest 行已有 `baseline_window`，可以在策略里用 W 里的窗口数集合判定「窗口语境里的数字」——若能下沉则卡侧函数删除。
3. 不再有自己的 T1 剥离、日期抽取、数字抽取。`_blank_card_times` 的职责改为在 manifest 构建期把卡上时刻登记进 W。

结果：**harness 的 `numerics_audit` 与卡侧结论必然一致**（同一函数、同一 manifest）。缓存记录只存一份审计对象；UI 文案从它读。

### 3.3 `_body_numeric_atoms` 里的魔数

`atoms.update({"7", "12"})` 删除。替代：`build_fact_card_numerics_manifest` 在登记 `baseline_window` 时，同时登记该窗口在文案层的口语化数字（`365d` → 12 个月；`7d`/`n/7` 来自卡的 `coverage` 分母）。派生规则放 manifest 构建器，来源是卡字段，不是常量集合。

### 3.4 上下文块与 manifest 格式对齐

`build_fact_card_context_block` 的 `value` / `baseline_mean` 输出改为与 manifest 相同的格式化字串（或 manifest 反过来登记原值两种形态）。二选一，选后者更稳：模型看见什么形态都能对上。

### 3.5 Tier0 `min` 档

现状：`_compress_fact_card_context` 在 `min` 把 6074 字符压到 190 并写 `metrics omitted`，与 TASK「非空必引用」自相矛盾。处理：

- 优先：在 `harness_profile_registry` 为 `fact_card_interpret` 声明 **FACT_CARD_CONTEXT 的最低档为 `summary`**（配置项，不是 `if profile == ...`）；预算不够时先压 `USER_ASSESSMENT_PROMPT` 以外的通用槽。
- 若 registry 没有「槽位地板」概念，则 `min` 档保留每行 `[label, value, unit, day]` 的紧凑数组，绝不清空 metrics。
- selfcheck：`min` 档输出必须仍含每一行的 `value`。

---

## 4. TASK 文本（profile 层）

改 `harness_plan._FACT_CARD_INTERPRET_TASK`，原则：

1. **分条编号**，不再是一段 1k 字符英文。7b 对编号规则的遵循明显好于长段。
2. 数字规则改写为三级，与 §2.3 一致：
   - 你自己的数据：只能写 manifest / 上下文里出现的数字和日期，小数原样照抄；
   - 一般人群常识与训练建议：可以写整数（如 95%、70–80%、2–3 次），**不要写小数**；想标注来源用 T1 块；
   - 绝对日期只能是 as_of / calendar_day / 各行 day。
3. **T1 模板按 response_locale 给**：TASK 里放占位符（如 `{T1_TEMPLATE}`），Tier0 装配时从 `LANG_DISCLOSURE_MAP` 取对应语言的示例。TASK 源码里不再有中文模板字面量。
4. 通用约束（纯文本、无诊断、语言跟随 locale、不重复免责声明）若 profile 通用层已有对应槽位或 tail，就移到通用层；TASK 只保留：大纲 = USER_ASSESSMENT_PROMPT、点名只谈点名、非空必引用、数字三级、窗口措辞一致。
5. 缓存键：`_INTERPRET_PROMPT_REV` 手工字串改为 `sha256(TASK 文本 + 策略版本号)[:12]`，TASK 一变自动失效。策略版本号放 `numerics_manifest` 的策略常量旁。

---

## 5. 失败态与可观测性

1. `failed` 缓存记录新增 `rejected_text`（本机数据，FR-6.6 已允许显示被拒 token；原文也是同一性质）。日志里 `turn_complete … numerics=FAIL` 行同时打出 violations 与文本前 200 字。
2. UI 文案（`fact_card_copy`）：violations 去重、按类别归并——「卡上没有的测量值：65 bpm」「不在卡上的日期：2026-09-05」「参考标准块里写了你的数据」。不再把 `2、95、2、3、95` 原样丢给用户。
3. 连续两次同键失败后，按钮下多一行提示（中英各一句，进 `fact_card_copy`）：「解读只能引用卡上的数字；一般常识可写整数，不要写小数。」这是期望管理，不是重试逻辑。
4. telemetry：审计对象新增 `educational_ints`（放行的 E 级整数列表），用于观察放宽后有没有漏网。

---

## 6. selfcheck（行为测试，替换文本断言）

`scripts/pha_fact_card_selfcheck.py`：

- 删除对 TASK 文本的字面断言（含 "outline"、不含 `FACT_CARD_CONTEXT.focus`）。TASK 是 profile 的产物，测它的行为不是它的措辞。保留一条：TASK 源码里不含任何 `【参考标准` / `[Reference Standard` 字面量（防模板回流硬编码）。
- 新增 §2.4 全部 18 条为参数化用例，中英各跑一遍（英文卡 label 换成 `label_en`）。
- 新增不变式：对同一 `(text, card)`，`chat_service` 回传的 `numerics_audit.passed` 与卡侧最终 `status` 必须一致（消灭「harness ok、卡侧拒」）。
- `min` 档上下文仍含每行 `value`。
- `build_fact_card_context_block` 输出的每个数值字串都 ∈ W（自洽）。

`scripts/pha_numerics_manifest_selfcheck.py`：

- fact-card 策略下的 6 条规则各至少一例；`t0_forgery_in_t1_block` 中英各一例；标识符遮罩一例；`.0` / 千分位归一一例。
- 现有 strict / t0_plus_disclosure 用例全部不变（回归门）。

`scripts/pha_chat_turn_fsm_selfcheck.py`：`fact_card_interpret` 槽序与 registry `--write` 不变即可。

---

## 7. 历史整理（commit 8462695）

未推送，可安全改写。**决定：`git commit --amend`**，把工作区的撤回一起并进去，message 改为如实描述：

```
Fact-card interpretation: dedicated profile, card manifest, locale rendering

- fact_card_interpret profile; Numerics Manifest built from the day's card
- USER_ASSESSMENT_PROMPT is the outline (TASK-level); no metric-id parsing
- locale-aware dates/labels, plain-text output, cache key with locale
- healthkit priority pack 1 (SpO2 / RR / VO2max / wrist temp), zip as truth
```

不要在 message 里保留「fails closed on off-focus numbers」这类描述。amend 后 `git log -1 --stat` 应仍是 46±9 个文件。若维护者不愿改写历史，则改为新 commit，message 第一行必须写「Revert focus filtering from 8462695; outline lives in TASK」。

本文（P9.4）的代码改动**另起 commit**，不与上面合并。

---

## 8. 文档改动清单（随 P9.4 代码同 PR）

| 文件 | 改什么 |
|---|---|
| `prd-pha-ios-proactive-agent-v1.md` | 本文落笔时已改：FR-6.3 / FR-6.10 分级、§8 M1-P9.4、§11、§12 v1.10。代码落地后把 P9.4 置 DONE |
| `manifest-tier-v1.md` | §3.2 后加一小节「fact_card 策略」指向本文 §2.3，声明子句级 P/E/M 判定与 `educational_int` telemetry；策略表加一行 |
| `pha-fact-card.md` | 「解读」行：审计 = harness 单一审计（fact_card 策略）；不再写「原子数审计」 |
| `harness-change-log.md` | 类别 P1（audit）：fact_card 策略、词表扩键、标识符遮罩、归一化；回滚方式 |
| `pha-ios-proactive-change-log.md` | P9.4 落地条目；失败态文案变化 |
| `handoff-…-v2.md` §4.4 | 已加「被 v3 取代」指针 |

---

## 9. 执行顺序（按序打勾，每步 selfcheck 绿再下一步）

1. `git commit --amend`（§7），确认 `git status` 干净。
2. `numerics_manifest.py`：归一化 + 标识符遮罩 + `LANG_T0_CLAIM_MAP` 扩键 + fact_card 策略 + `educational_ints`。先写 `pha_numerics_manifest_selfcheck.py` 用例再实现。
3. `build_fact_card_numerics_manifest`：登记 `.0` 双形态、卡上时刻、窗口口语数（删 `{"7","12"}`）。
4. `fact_card_interpret.py`：审计函数收缩为委托（§3.2），删除全部字面量正则；`rejected_text` 入缓存；`_INTERPRET_PROMPT_REV` 改哈希。
5. `harness_plan.py` TASK 分条 + `{T1_TEMPLATE}` 占位；`harness_tier0_assembly.py` 按 locale 填充；`min` 档地板（§3.5）；registry `--write`。
6. `fact_card_copy.py` 失败文案归并去重 + 两次失败提示，中英。
7. `pha_fact_card_selfcheck.py` 换成行为用例（§6）；三套 selfcheck 全绿。
8. 清空 `data/fact_card_interpret/`；`bash scripts/pha_restart_accept.sh`；Mac 浏览器 + iPhone Safari 各点一次「生成解读」，中英各一次；把四次结果（含 `educational_ints`）贴进 change-log。
9. 文档（§8）；commit。

---

## 10. 不要做的事

- 不要在任何 Python 文件里出现指标名（`SpO2`、`VO2max`、`静息心率`）作为审计逻辑的一部分。
- 不要恢复 ≥100、≤2 位、0.5–15 之类的数值形态阈值作为放行条件（小数=S 是唯一形态规则，且是**收紧**不是放行）。
- 不要保留两套数字抽取；卡侧删干净。
- 不要用整句做语境判定。
- 不要把 T1 中文模板写回 TASK 源码。
- 不要为了让 7b 通过而在 TASK 里列举本卡的指标名。
- 不要自动重试（P9.4b 未拍板）。

---

## 11. 需要维护者拍板（附默认值，未回复即按默认执行）

| # | 问题 | 默认 |
|---|---|---|
| 1 | 8462695 用 amend 还是新 commit | amend（未推送） |
| 2 | 小数一律 S 级（含「建议 7.5 小时」） | 是 |
| 3 | 规则 5「卡标签/单位 + 无教育词 → 拒」是否过严 | 保留；观察 `educational_ints` 与真机失败率两周再议 |
| 4 | P9.4b 自动修复轮（失败后把 violations 回灌、再调一次模型、仍失败才显示失败态） | 不做；登记 §11，M3 前再议 |
| 5 | 失败记录存原文 `rejected_text` | 存（本机数据） |
| 6 | 焦点跑偏（评估点名仍念 SpO2/呼吸率） | → [`handoff-2026-09-08-fact-card-interpret-v4-soul.md`](handoff-2026-09-08-fact-card-interpret-v4-soul.md)（M1-P9.5 专用 soul） |
